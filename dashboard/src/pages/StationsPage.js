import React, { useState, useEffect } from 'react';
import api from '../services/api';

const StationsPage = () => {
    const [stations, setStations] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStations = async () => {
            try {
                const response = await api.get('/api/stations/');
                setStations(response.data);
            } catch (err) {
                console.error('Failed to fetch stations', err);
            } finally {
                setLoading(false);
            }
        };
        fetchStations();
    }, []);

    return (
        <div>
            <h1 style={{ marginBottom: '2rem' }}>Monitoring Stations</h1>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
                        <tr>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>ID</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Location Name</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Zone Type</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Status</th>
                            <th style={{ padding: '1rem 1.5rem', fontWeight: 600, fontSize: '0.875rem' }}>Coordinates</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan="5" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading stations...</td></tr>
                        ) : (
                            stations.map((s) => (
                                <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', fontWeight: 600 }}>{s.id}</td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem' }}>{s.name}</td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', textTransform: 'capitalize' }}>{s.zone}</td>
                                    <td style={{ padding: '1rem 1.5rem' }}>
                                        <span style={{
                                            padding: '0.25rem 0.625rem',
                                            borderRadius: '99px',
                                            fontSize: '0.75rem',
                                            fontWeight: 600,
                                            background: s.status === 'online' ? '#d1fae5' : '#fef2f2',
                                            color: s.status === 'online' ? '#059669' : '#b91c1c'
                                        }}>
                                            {s.status}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                                        {s.latitude.toFixed(4)}, {s.longitude.toFixed(4)}
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

export default StationsPage;
