import pytest
from app import create_app
from app.database import db
from app.models.user import User
from app.models.project import Project
from app.models.file_metadata import ProjectFile
from app.models.indexing_job import IndexingJob
from app.models.conversation import Conversation, Message, MessageCitation
from app.services.project_repository import ProjectRepository
from app.services.conversation_repository import ConversationRepository
from app.utils.security import hash_password, check_password


@pytest.fixture
def test_app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test_models.db').as_posix()}",
        "STORAGE_DIR": tmp_path / "storage"
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_user_model(test_app):
    with test_app.app_context():
        pw_hash = hash_password("mypassword123")
        user = User(email="coder@example.com", password_hash=pw_hash, full_name="Coder Test")
        db.session.add(user)
        db.session.commit()

        assert user.id is not None
        assert user.email == "coder@example.com"
        assert check_password("mypassword123", user.password_hash)
        assert not check_password("wrongpass", user.password_hash)
        assert user.created_at is not None
        assert user.updated_at is not None

        # Test duplicate email rejection
        duplicate_user = User(email="coder@example.com", password_hash=pw_hash)
        db.session.add(duplicate_user)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_project_model_and_cascade_delete(test_app):
    with test_app.app_context():
        user = User(email="owner@test.com", password_hash=hash_password("pass123"))
        db.session.add(user)
        db.session.commit()

        # Create project
        proj = Project(
            name="Alpha Project",
            description="Test repo",
            user_id=user.id,
            source_type="zip",
            storage_path="/tmp/test_storage"
        )
        db.session.add(proj)
        db.session.commit()

        # Add project file
        pf = ProjectFile(
            project_id=proj.id,
            file_path="src/index.js",
            file_type="javascript",
            content_hash="abc123sha256hash",
            file_size=1024,
            line_count=45
        )
        db.session.add(pf)

        # Add indexing job
        job = IndexingJob(
            project_id=proj.id,
            status="completed",
            progress_percentage=100,
            total_files=1,
            processed_files=1
        )
        db.session.add(job)

        # Add conversation, message, citation
        conv = Conversation(project_id=proj.id, user_id=user.id, title="Architecture QA")
        db.session.add(conv)
        db.session.commit()

        msg = Message(conversation_id=conv.id, role="assistant", content="Here is the explanation.")
        msg.set_metadata({"tokens": 150})
        db.session.add(msg)
        db.session.commit()

        cit = MessageCitation(
            message_id=msg.id,
            file_path="src/index.js",
            start_line=10,
            end_line=25,
            snippet="console.log('hello')"
        )
        db.session.add(cit)
        db.session.commit()

        # Verify child records exist
        assert ProjectFile.query.filter_by(project_id=proj.id).count() == 1
        assert IndexingJob.query.filter_by(project_id=proj.id).count() == 1
        assert Conversation.query.filter_by(project_id=proj.id).count() == 1
        assert Message.query.filter_by(conversation_id=conv.id).count() == 1
        assert MessageCitation.query.filter_by(message_id=msg.id).count() == 1

        # Delete project and assert cascade
        db.session.delete(proj)
        db.session.commit()

        assert ProjectFile.query.filter_by(project_id=proj.id).count() == 0
        assert IndexingJob.query.filter_by(project_id=proj.id).count() == 0
        assert Conversation.query.filter_by(project_id=proj.id).count() == 0
        assert Message.query.filter_by(conversation_id=conv.id).count() == 0
        assert MessageCitation.query.filter_by(message_id=msg.id).count() == 0


def test_project_file_unique_constraint(test_app):
    with test_app.app_context():
        proj = Project(name="Constraint Test", storage_path="/tmp/test")
        db.session.add(proj)
        db.session.commit()

        pf1 = ProjectFile(project_id=proj.id, file_path="app.py", file_type="python")
        db.session.add(pf1)
        db.session.commit()

        # Same file path under same project must fail
        pf2 = ProjectFile(project_id=proj.id, file_path="app.py", file_type="python")
        db.session.add(pf2)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_user_isolation_security(test_app):
    with test_app.app_context():
        user_alice = User(email="alice@test.com", password_hash=hash_password("alicepass"))
        user_bob = User(email="bob@test.com", password_hash=hash_password("bobpass"))
        db.session.add_all([user_alice, user_bob])
        db.session.commit()

        # Alice creates a project
        alice_proj = ProjectRepository.create_project(
            name="Alice Secret Project",
            user_id=user_alice.id,
            storage_path="/tmp/alice"
        )

        # Alice creates a conversation
        alice_conv = ConversationRepository.create_conversation(
            project_id=alice_proj.id,
            user_id=user_alice.id,
            title="Alice Private Discussion"
        )

        # 1. Alice can access her own project
        proj, err = ProjectRepository.get_project_secure(alice_proj.id, user_alice.id)
        assert err is None
        assert proj.id == alice_proj.id

        # 2. Bob CANNOT access Alice's project (Forbidden)
        _, bob_err = ProjectRepository.get_project_secure(alice_proj.id, user_bob.id)
        assert bob_err == "forbidden"

        # 3. Bob CANNOT access Alice's conversation
        _, conv_err = ConversationRepository.get_conversation_secure(alice_conv.id, user_bob.id)
        assert conv_err == "forbidden"

        # 4. Bob cannot delete Alice's project
        success, del_err = ProjectRepository.delete_project_secure(alice_proj.id, user_bob.id)
        assert success is False
        assert del_err == "forbidden"

        # Project still exists
        assert db.session.get(Project, alice_proj.id) is not None
