import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useNavigate } from 'react-router-dom';

const ViolationsPage = () => {
    const [violations, setViolations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({ tier: '', status: '' });
    const navigate = useNavigate();

    useEffect(() => {
        fetchViolations();
    }, [filters]);

    const fetchViolations = async () => {
        setLoading(true);
        try {
            const params = {};
            if (filters.tier) params.tier = filters.tier;
            if (filters.status) params.status = filters.status;

            const response = await api.get('/api/violations/', { params });
            setViolations(response.data.items);
        } catch (err) {
            console.error('Failed to fetch violations', err);
        } finally {
            setLoading(false);
        }
    };

    const getTierColor = (tier) => {
        switch (tier) {
            case 'VIOLATION': return 'var(--tier-3)';
            case 'FLAG': return 'var(--tier-2)';
            case 'MONITOR': return 'var(--tier-1)';
            default: return 'var(--text-muted)';
        }
    };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <h1>Compliance Violations</h1>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <select
                        className="input-field"
                        style={{ width: '160px', padding: '0.5rem' }}
                        value={filters.tier}
                        onChange={(e) => setFilters({ ...filters, tier: e.target.value })}
                    >
                        <option value="">All Tiers</option>
                        <option value="VIOLATION">Tier 3 (Violation)</option>
                        <option value="FLAG">Tier 2 (Flag)</option>
                        <option value="MONITOR">Tier 1 (Monitor)</option>
                    </select>
                    <select
                        className="input-field"
                        style={{ width: '160px', padding: '0.5rem' }}
                        value={filters.status}
                        onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                    >
                        <option value="">All Statuses</option>
                        <option value="OPEN">Open</option>
                        <option value="ESCALATED">Escalated</option>
                        <option value="DISMISSED">Dismissed</option>
                    </select>
                </div>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
                        <tr>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Station</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Pollutant</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Tier</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Value</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Status</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Time</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}></th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan="7" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading records...</td></tr>
                        ) : violations.length === 0 ? (
                            <tr><td colSpan="7" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>No compliance events found.</td></tr>
                        ) : (
                            violations.map((v) => (
                                <tr key={v.id} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => navigate(`/violations/${v.id}`)}>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', fontWeight: 500 }}>{v.station_id}</td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem' }}>{v.pollutant}</td>
                                    <td style={{ padding: '1rem 1.5rem' }}>
                                        <span style={{
                                            padding: '0.25rem 0.625rem',
                                            borderRadius: '99px',
                                            fontSize: '0.75rem',
                                            fontWeight: 700,
                                            background: `${getTierColor(v.tier)}15`,
                                            color: getTierColor(v.tier),
                                            border: `1px solid ${getTierColor(v.tier)}40`
                                        }}>
                                            {v.tier}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem' }}>
                                        {v.observed_value.toFixed(1)} <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>/ {v.limit_value}</span>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem' }}>
                                        <span style={{
                                            color: v.status === 'OPEN' ? '#b91c1c' : '#059669',
                                            fontWeight: 600,
                                            fontSize: '0.75rem'
                                        }}>
                                            ● {v.status}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                                        {new Date(v.created_at).toLocaleString()}
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', textAlign: 'right' }}>
                                        <button style={{ color: 'var(--primary)', fontWeight: 600, fontSize: '0.875rem' }}>View Details →</button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ViolationsPage;
