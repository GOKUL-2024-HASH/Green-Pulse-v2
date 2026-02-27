import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const LoginPage = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setBusy(true);
        try {
            await login(email, password);
            navigate('/');
        } catch (err) {
            setError('Invalid credentials. Please check your email and password.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%)'
        }}>
            <div className="card" style={{ width: '400px', padding: '3rem' }}>
                <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                    <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🌿 GreenPulse</h1>
                    <p style={{ color: 'var(--text-muted)' }}>Compliance Monitoring Suite</p>
                </div>

                {error && (
                    <div style={{
                        background: '#fee2e2',
                        color: '#b91c1c',
                        padding: '0.75rem',
                        borderRadius: '8px',
                        marginBottom: '1rem',
                        fontSize: '0.875rem'
                    }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 500 }}>Email Address</label>
                        <input
                            className="input-field"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="admin@greenpulse.in"
                            required
                        />
                    </div>
                    <div style={{ marginBottom: '2rem' }}>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 500 }}>Password</label>
                        <input
                            className="input-field"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                        />
                    </div>
                    <button
                        className="btn-primary"
                        style={{ width: '100%' }}
                        disabled={busy}
                    >
                        {busy ? 'Authenticating...' : 'Sign In'}
                    </button>
                </form>
            </div>
        </div >
    );
};

export default LoginPage;
