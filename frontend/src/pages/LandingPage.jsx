import React from 'react';
import { 
  Code2, 
  TerminalSquare, 
  Search, 
  MessageSquare, 
  FileCode, 
  GitBranch, 
  ChevronRight,
  Menu,
  X,
  Sparkles
} from 'lucide-react';

export default function LandingPage({ onNavigate }) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
    setIsMobileMenuOpen(false);
  };

  return (
    <div className="landing-page">
      {/* 1. Navigation Bar */}
      <nav className="landing-nav">
        <div className="landing-container nav-container">
          <div className="landing-brand">
            <div className="brand-icon">
              <Code2 size={18} />
            </div>
            <span className="brand-title">AI Developer Assistant</span>
          </div>

          {/* Desktop Nav */}
          <div className="landing-nav-links desktop-only">
            <button className="nav-link" onClick={() => scrollToSection('features')}>Features</button>
            <button className="nav-link" onClick={() => scrollToSection('how-it-works')}>How It Works</button>
            <button className="nav-link" onClick={() => scrollToSection('benefits')}>Benefits</button>
          </div>

          <div className="landing-nav-actions desktop-only">
            <button className="btn btn-ghost" onClick={() => onNavigate('login')}>Sign In</button>
            <button className="btn btn-primary" onClick={() => onNavigate('register')}>Get Started</button>
          </div>

          {/* Mobile Nav Toggle */}
          <button 
            className="mobile-menu-btn mobile-only" 
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Nav Menu */}
        {isMobileMenuOpen && (
          <div className="mobile-nav-menu">
            <button className="nav-link" onClick={() => scrollToSection('features')}>Features</button>
            <button className="nav-link" onClick={() => scrollToSection('how-it-works')}>How It Works</button>
            <button className="nav-link" onClick={() => scrollToSection('benefits')}>Benefits</button>
            <hr className="nav-divider" />
            <button className="btn btn-secondary btn-full" onClick={() => onNavigate('login')}>Sign In</button>
            <button className="btn btn-primary btn-full" onClick={() => onNavigate('register')}>Get Started</button>
          </div>
        )}
      </nav>

      <main>
        {/* 2. Hero Section */}
        <section className="hero-section">
          <div className="landing-container hero-container">
            <div className="hero-content">
              <h1 className="hero-title">Your AI Assistant Understands Your Codebase.</h1>
              <p className="hero-subtitle">
                Upload your project, ask complex architecture questions, search semantic context, and generate comprehensive tests—all instantly grounded in your actual source code.
              </p>
              <div className="hero-actions">
                <button className="btn btn-primary btn-lg" onClick={() => onNavigate('register')}>
                  Get Started <ChevronRight size={16} />
                </button>
                <button className="btn btn-secondary btn-lg" onClick={() => scrollToSection('features')}>
                  Explore Features
                </button>
              </div>
            </div>

            {/* UI Preview (Fake Window) */}
            <div className="hero-preview-wrapper">
              <div className="ui-preview-window">
                <div className="ui-preview-header">
                  <div className="window-controls">
                    <span className="dot red"></span>
                    <span className="dot yellow"></span>
                    <span className="dot green"></span>
                  </div>
                  <div className="window-title">AI Developer Workspace Preview</div>
                </div>
                <div className="ui-preview-body">
                  <div className="ui-preview-sidebar">
                    <div className="mock-line" style={{width: '60%'}}></div>
                    <div className="mock-line" style={{width: '80%'}}></div>
                    <div className="mock-line" style={{width: '50%'}}></div>
                    <div className="mock-line" style={{width: '70%'}}></div>
                  </div>
                  <div className="ui-preview-editor">
                    <div className="mock-code">
                      <span className="keyword">function</span> <span className="entity">analyzeCodebase</span>() {'{'}
                      <br/>
                      &nbsp;&nbsp;<span className="keyword">const</span> context = <span className="keyword">await</span> getVectorEmbeddings();
                      <br/>
                      &nbsp;&nbsp;<span className="keyword">return</span> generateInsights(context);
                      <br/>
                      {'}'}
                    </div>
                  </div>
                  <div className="ui-preview-chat">
                    <div className="mock-bubble assistant">
                      Here's an analysis of the codebase architecture...
                    </div>
                    <div className="mock-bubble user">
                      Where is the authentication middleware located?
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Core Features Section */}
        <section id="features" className="features-section">
          <div className="landing-container">
            <h2 className="section-title text-center">Supercharge Your Development Workflow</h2>
            <div className="features-grid">
              <div className="feature-card">
                <div className="feature-icon"><MessageSquare size={20} /></div>
                <h3>Project-Aware AI Chat</h3>
                <p>Chat naturally with an AI that has complete context of your entire repository, not just single files.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><Search size={20} /></div>
                <h3>Semantic Code Search</h3>
                <p>Find what you need by describing intent rather than matching exact keywords or regex strings.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><TerminalSquare size={20} /></div>
                <h3>Explanation & Debugging</h3>
                <p>Instantly explain complex legacy logic or identify subtle race conditions and unhandled errors.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><FileCode size={20} /></div>
                <h3>Generate Tests & Docs</h3>
                <p>Automatically write comprehensive unit tests and inline documentation tailored to your exact code style.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><Code2 size={20} /></div>
                <h3>Source Citations</h3>
                <p>Every answer includes clickable line-number references, ensuring trust and rapid navigation.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><GitBranch size={20} /></div>
                <h3>GitHub Integration</h3>
                <p>Seamlessly import any public repository directly into your workspace with a single URL.</p>
              </div>
            </div>
          </div>
        </section>

        {/* 4. How It Works Section */}
        <section id="how-it-works" className="how-it-works-section">
          <div className="landing-container">
            <h2 className="section-title text-center">How It Works</h2>
            <div className="steps-container">
              <div className="step-card">
                <div className="step-number">1</div>
                <h3>Connect Codebase</h3>
                <p>Upload a ZIP file or import a GitHub repository directly into the platform.</p>
              </div>
              <div className="step-card">
                <div className="step-number">2</div>
                <h3>Instant Indexing</h3>
                <p>Our engine chunks your code and builds a FAISS vector index for deep semantic retrieval.</p>
              </div>
              <div className="step-card">
                <div className="step-number">3</div>
                <h3>Ask & Discover</h3>
                <p>Ask questions and receive precise, AI-generated answers grounded by real source file citations.</p>
              </div>
            </div>
          </div>
        </section>

        {/* 5. Benefits Section */}
        <section id="benefits" className="benefits-section">
          <div className="landing-container benefits-container">
            <div className="benefits-content">
              <h2 className="section-title">Reduce Onboarding Time and Technical Debt</h2>
              <p className="benefits-text">
                Navigating an unfamiliar, undocumented codebase can take days. AI Developer Assistant acts as a senior engineer who has memorized every file. 
              </p>
              <ul className="benefits-list">
                <li><ChevronRight size={16} className="text-accent"/> Understand complex architectures in minutes.</li>
                <li><ChevronRight size={16} className="text-accent"/> Trace hard-to-find bugs across multiple microservices.</li>
                <li><ChevronRight size={16} className="text-accent"/> Automate the repetitive creation of boilerplate tests.</li>
              </ul>
            </div>
            <div className="benefits-visual">
              <div className="pulse-circle">
                <Sparkles size={40} className="text-accent" />
              </div>
            </div>
          </div>
        </section>

        {/* 6. Call-to-action Section */}
        <section className="cta-section">
          <div className="landing-container text-center">
            <h2 className="section-title">Ready to understand your code?</h2>
            <p className="cta-subtitle">Join developers building better software, faster.</p>
            <button className="btn btn-primary btn-xl" onClick={() => onNavigate('register')}>
              Get Started Now
            </button>
          </div>
        </section>
      </main>

      {/* 7. Footer */}
      <footer className="landing-footer">
        <div className="landing-container footer-container">
          <div className="footer-brand">
            <div className="brand-icon">
              <Code2 size={16} />
            </div>
            <span className="brand-title">AI Developer Assistant</span>
          </div>
          <div className="footer-links">
            <button className="btn-ghost" onClick={() => scrollToSection('features')}>Features</button>
            <button className="btn-ghost" onClick={() => scrollToSection('how-it-works')}>How it Works</button>
            <a href="#" className="btn-ghost" style={{textDecoration: 'none'}}>Privacy Policy</a>
            <a href="#" className="btn-ghost" style={{textDecoration: 'none'}}>Terms of Service</a>
          </div>
        </div>
        <div className="footer-bottom text-center">
          &copy; {new Date().getFullYear()} AI Developer Assistant. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
