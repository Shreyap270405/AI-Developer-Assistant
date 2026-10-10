import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff } from 'lucide-react';

export default function RegisterPage({ onSwitchToLogin }) {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const errors = {};
    if (!fullName.trim()) errors.fullName = 'Name is required';
    if (!email.trim() || !email.includes('@')) errors.email = 'Valid email is required';
    if (password.length < 6) errors.password = 'Password must be at least 6 characters';
    if (password !== confirm) errors.confirm = 'Passwords do not match';
    
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    if (!validate()) {
      return;
    }

    setLoading(true);
    try {
      await register(email, password, fullName);
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getFieldErrorMsg = (fieldName) => {
    return fieldErrors[fieldName] ? (
      <span style={{ color: 'var(--rose)', fontSize: '11px', marginTop: '4px' }}>
        {fieldErrors[fieldName]}
      </span>
    ) : null;
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="auth-icon">⬡</span>
          <h1 className="auth-title">AI Developer Assistant</h1>
          <p className="auth-subtitle">Project-Aware GenAI Workspace</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <h2 className="form-heading">Create your account</h2>

          {error && <p className="auth-error" role="alert">{error}</p>}

          <div className="field-group">
            <label htmlFor="reg-name" className="field-label">Full Name</label>
            <input
              id="reg-name"
              type="text"
              className={`field-input ${fieldErrors.fullName ? 'error' : ''}`}
              style={fieldErrors.fullName ? { borderColor: 'var(--rose)' } : {}}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Smith"
              autoComplete="name"
            />
            {getFieldErrorMsg('fullName')}
          </div>

          <div className="field-group">
            <label htmlFor="reg-email" className="field-label">Email</label>
            <input
              id="reg-email"
              type="email"
              className={`field-input ${fieldErrors.email ? 'error' : ''}`}
              style={fieldErrors.email ? { borderColor: 'var(--rose)' } : {}}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
            {getFieldErrorMsg('email')}
          </div>

          <div className="field-group">
            <label htmlFor="reg-password" className="field-label">Password</label>
            <div className="password-input-wrapper" style={{ position: 'relative' }}>
              <input
                id="reg-password"
                type={showPassword ? 'text' : 'password'}
                className={`field-input ${fieldErrors.password ? 'error' : ''}`}
                style={{ 
                  paddingRight: '40px', 
                  width: '100%',
                  ...(fieldErrors.password ? { borderColor: 'var(--rose)' } : {})
                }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 6 characters"
                autoComplete="new-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex="-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {getFieldErrorMsg('password')}
          </div>

          <div className="field-group">
            <label htmlFor="reg-confirm" className="field-label">Confirm Password</label>
            <div className="password-input-wrapper" style={{ position: 'relative' }}>
              <input
                id="reg-confirm"
                type={showConfirm ? 'text' : 'password'}
                className={`field-input ${fieldErrors.confirm ? 'error' : ''}`}
                style={{ 
                  paddingRight: '40px', 
                  width: '100%',
                  ...(fieldErrors.confirm ? { borderColor: 'var(--rose)' } : {})
                }}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Repeat password"
                autoComplete="new-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowConfirm(!showConfirm)}
                tabIndex="-1"
                aria-label={showConfirm ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                }}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {getFieldErrorMsg('confirm')}
          </div>

          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? 'Creating account…' : 'Create Account'}
          </button>

          <p className="auth-switch">
            Already have an account?{' '}
            <button type="button" className="link-btn" onClick={onSwitchToLogin}>
              Sign in
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
