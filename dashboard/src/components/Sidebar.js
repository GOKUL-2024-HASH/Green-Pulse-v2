import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Sidebar = () => {
    const { user, logout } = useAuth();

    const navItems = [
        { path: '/', label: 'Overview', icon: '📊' },
        { path: '/violations', label: 'Violations', icon: '🚨' },
        { path: '/stations', label: 'Stations', icon: '📍' },
    ];

    return (
        <div style={{
            width: '260px',
            height: '100vh',
            background: 'white',
            borderRight: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            position: 'fixed'
        }}>
            <div style={{ padding: '2rem', borderBottom: '1px solid var(--border)' }}>
                <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>🌿</span> GreenPulse
                </h2>
            </div>

            <nav style={{ flex: 1, padding: '1.5rem 1rem' }}>
                {navItems.map(item => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        style={({ isActive }) => ({
                            display: 'flex',
                            alignItems: 'center',
                            gap: '1rem',
                            padding: '0.875rem 1rem',
                            borderRadius: '8px',
                            marginBottom: '0.5rem',
                            fontWeight: 500,
                            color: isActive ? 'var(--primary)' : 'var(--text-muted)',
                            background: isActive ? 'var(--primary-light)' : 'transparent',
                            transition: 'all 0.2s'
                        })}
                    >
                        <span>{item.icon}</span>
                        {item.label}
                    </NavLink>
                ))}
            </nav>

            <div style={{ padding: '1.5rem', borderTop: '1px solid var(--border)' }}>
                <div style={{ marginBottom: '1rem' }}>
                    <p style={{ fontSize: '0.875rem', fontWeight: 600 }}>{user?.full_name}</p>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>{user?.role}</p>
                </div>
                <button
                    onClick={logout}
                    style={{
                        width: '100%',
                        padding: '0.5rem',
                        borderRadius: '6px',
                        background: '#fef2f2',
                        color: '#b91c1c',
                        fontSize: '0.875rem',
                        fontWeight: 500
                    }}
                >
                    Sign Out
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
