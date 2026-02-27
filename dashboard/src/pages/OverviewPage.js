import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import api from '../services/api';

// ── helpers ───────────────────────────────────────────────────────────────────
const NAAQS = { pm25: 60, pm10: 100, no2: 80, so2: 80 };

const tierColor = (tier) => {
    if (tier === 'VIOLATION') return '#e11d48';
    if (tier === 'FLAG') return '#f59e0b';
    return '#3b82f6';
};

const statusBg = (tier) => {
    if (tier === 'VIOLATION') return { background: '#fff1f2', color: '#e11d48', border: '1px solid #fda4af' };
    if (tier === 'FLAG') return { background: '#fffbeb', color: '#d97706', border: '1px solid #fcd34d' };
    return { background: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe' };
};

const pm25Color = (value) => value == null ? '#94a3b8' : value > 60 ? '#e11d48' : '#059669';

const formatAge = (isoStr) => {
    if (!isoStr) return '—';
    const diffMs = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
};

const last7Days = () => {
    const days = [];
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        days.push(d.toISOString().slice(0, 10));
    }
    return days;
};

// ── sub-components ────────────────────────────────────────────────────────────
const SectionTitle = ({ children }) => (
    <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#064e3b', marginBottom: '1rem' }}>
        {children}
    </h2>
);

const Badge = ({ tier }) => (
    <span style={{
        ...statusBg(tier),
        padding: '2px 10px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600,
        whiteSpace: 'nowrap'
    }}>
        {tier}
    </span>
);

const StatusDot = ({ status }) => (
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
            width: 9, height: 9, borderRadius: '50%',
            background: status === 'online' ? '#059669' : '#e11d48',
            display: 'inline-block', flexShrink: 0
        }} />
        <span style={{
            fontSize: '0.8rem', fontWeight: 500,
            color: status === 'online' ? '#059669' : '#e11d48'
        }}>
            {status}
        </span>
    </span>
);

// ── Main Page ─────────────────────────────────────────────────────────────────
const OverviewPage = () => {
    const navigate = useNavigate();

    const [kpis, setKpis] = useState({ violations: 0, stations: 0, score: null });
    const [violations, setViolations] = useState([]);
    const [stations, setStations] = useState([]);
    const [pollutantAvgs, setPollutantAvgs] = useState({});
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchAll = useCallback(async () => {
        try {
            const [summaryRes, violsRes, stationsRes] = await Promise.all([
                api.get('/api/violations/summary'),
                api.get('/api/violations/', { params: { limit: 5 } }),
                api.get('/api/stations/'),
            ]);

            // KPIs
            const summary = summaryRes.data;
            const total = summary.total || 0;
            const onlineCount = (stationsRes.data || []).filter(s => s.status === 'online').length;
            const score = total === 0 ? 100 : Math.max(0, Math.round(100 - (total * 4)));
            setKpis({ violations: total, stations: onlineCount, score });

            // Recent violations
            setViolations(violsRes.data.items || []);

            // Stations
            setStations(stationsRes.data || []);

            // 7-day chart: fetch with wider window
            const fromDate = new Date();
            fromDate.setDate(fromDate.getDate() - 7);
            const allViolsRes = await api.get('/api/violations/', {
                params: { limit: 200, status: 'PENDING_OFFICER_REVIEW,ESCALATED,DISMISSED,RESOLVED,VIOLATION' }
            });
            const allViols = allViolsRes.data.items || [];

            // Group by date
            const days = last7Days();
            const countByDate = {};
            days.forEach(d => { countByDate[d] = 0; });
            allViols.forEach(v => {
                const day = (v.created_at || '').slice(0, 10);
                if (countByDate[day] !== undefined) countByDate[day]++;
            });
            setChartData(days.map(d => ({
                date: d.slice(5), // MM-DD
                violations: countByDate[d],
            })));

            // Pollutant averages — normalize names (API returns 'PM2.5' or 'pm25')
            const readings = allViols.filter(v => v.tier === 'VIOLATION' || v.tier === 'FLAG' || v.tier === 'MONITOR');
            const normalise = (p) => (p || '').toLowerCase().replace('.', '').replace('_', '');
            const avgs = {};
            ['pm25', 'pm10', 'no2', 'so2'].forEach(p => {
                const vals = readings
                    .filter(v => normalise(v.pollutant) === p && v.observed_value != null)
                    .map(v => v.observed_value);
                avgs[p] = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10 : null;
            });
            setPollutantAvgs(avgs);

        } catch (err) {
            console.error('Overview fetch failed:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
        const timer = setInterval(fetchAll, 60000);
        return () => clearInterval(timer);
    }, [fetchAll]);

    // ── styles ────────────────────────────────────────────────────────────────
    const s = {
        page: { display: 'flex', flexDirection: 'column', gap: '1.75rem' },
        row: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' },
        grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' },
        table: { width: '100%', borderCollapse: 'collapse' },
        th: {
            textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, color: '#64748b',
            textTransform: 'uppercase', letterSpacing: '0.05em', padding: '0.5rem 0.75rem',
            borderBottom: '1px solid #e2e8f0'
        },
        td: {
            padding: '0.75rem 0.75rem', fontSize: '0.85rem', borderBottom: '1px solid #f1f5f9',
            color: '#334155'
        },
        trHover: { cursor: 'pointer', transition: 'background 0.15s' },
        empty: { textAlign: 'center', padding: '2.5rem', color: '#94a3b8', fontSize: '0.9rem' },
        kpiCard: {
            background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '1.5rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
        },
        pollCard: {
            background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12,
            padding: '1.25rem 1.5rem', flex: 1
        },
    };

    return (
        <div style={s.page}>
            {/* ── Header ── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#064e3b' }}>
                    Dashboard Overview
                </h1>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    Auto-refreshes every 60s
                </span>
            </div>

            {/* ── KPI Cards ── */}
            <div style={s.row}>
                <div style={{ ...s.kpiCard, borderTop: '3px solid #e11d48' }}>
                    <p style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Active Violations
                    </p>
                    <h2 style={{ fontSize: '2.5rem', marginTop: '0.4rem', color: '#e11d48', fontWeight: 800 }}>
                        {loading ? '—' : kpis.violations}
                    </h2>
                </div>
                <div style={{ ...s.kpiCard, borderTop: '3px solid #059669' }}>
                    <p style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Stations Online
                    </p>
                    <h2 style={{ fontSize: '2.5rem', marginTop: '0.4rem', color: '#059669', fontWeight: 800 }}>
                        {loading ? '—' : kpis.stations}
                    </h2>
                </div>
                <div style={{ ...s.kpiCard, borderTop: '3px solid #3b82f6' }}>
                    <p style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Compliance Score
                    </p>
                    <h2 style={{ fontSize: '2.5rem', marginTop: '0.4rem', color: '#3b82f6', fontWeight: 800 }}>
                        {loading ? '—' : `${kpis.score}%`}
                    </h2>
                </div>
            </div>

            {/* ── Section 1 + 2 side by side ── */}
            <div style={s.grid2}>

                {/* Section 1: Recent Violations Table */}
                <div className="card">
                    <SectionTitle>Recent Violations</SectionTitle>
                    {loading ? (
                        <p style={s.empty}>Loading…</p>
                    ) : violations.length === 0 ? (
                        <p style={s.empty}>✅ No violations found</p>
                    ) : (
                        <table style={s.table}>
                            <thead>
                                <tr>
                                    {['Station', 'Pollutant', 'Value', 'Tier', 'Status', 'Time'].map(h => (
                                        <th key={h} style={s.th}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {violations.map(v => (
                                    <tr
                                        key={v.id}
                                        style={s.trHover}
                                        onClick={() => navigate(`/violations/${v.id}`)}
                                        onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                                        onMouseLeave={e => e.currentTarget.style.background = ''}
                                    >
                                        <td style={s.td}><strong>{v.station_id}</strong></td>
                                        <td style={s.td}>{(v.pollutant || '').toUpperCase()}</td>
                                        <td style={s.td}>{v.observed_value?.toFixed(1)}</td>
                                        <td style={{ ...s.td, color: tierColor(v.tier), fontWeight: 700 }}>{v.tier}</td>
                                        <td style={s.td}><Badge tier={v.tier} /></td>
                                        <td style={{ ...s.td, color: '#94a3b8' }}>{formatAge(v.created_at)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Section 2: Station Status */}
                <div className="card">
                    <SectionTitle>Station Status</SectionTitle>
                    {loading ? (
                        <p style={s.empty}>Loading…</p>
                    ) : (
                        <table style={s.table}>
                            <thead>
                                <tr>
                                    {['Station', 'Zone', 'PM2.5', 'Status'].map(h => (
                                        <th key={h} style={s.th}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {stations.map(st => {
                                    // Find latest PM2.5 from violations
                                    const latest = violations.find(
                                        v => v.station_id === st.id && v.pollutant === 'pm25'
                                    );
                                    const pm25 = latest?.observed_value ?? null;

                                    return (
                                        <tr key={st.id}>
                                            <td style={s.td}>
                                                <div style={{ fontWeight: 600 }}>{st.name}</div>
                                                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{st.id}</div>
                                            </td>
                                            <td style={s.td}>
                                                <span style={{
                                                    fontSize: '0.78rem', background: '#f1f5f9',
                                                    color: '#475569', borderRadius: 6, padding: '2px 8px'
                                                }}>
                                                    {(st.zone || 'N/A').replace('_', ' ')}
                                                </span>
                                            </td>
                                            <td style={{ ...s.td, color: pm25Color(pm25), fontWeight: 700 }}>
                                                {pm25 != null ? `${pm25.toFixed(1)} μg/m³` : '—'}
                                            </td>
                                            <td style={s.td}><StatusDot status={st.status || 'online'} /></td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>

            {/* ── Section 3: Pollutant Summary Cards ── */}
            <div className="card">
                <SectionTitle>Current Readings — All Stations</SectionTitle>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    {['pm25', 'pm10', 'no2', 'so2'].map(p => {
                        const val = pollutantAvgs[p];
                        const limit = NAAQS[p];
                        const over = val != null && val > limit;
                        return (
                            <div key={p} style={{
                                ...s.pollCard,
                                borderTop: `3px solid ${over ? '#e11d48' : '#059669'}`,
                                minWidth: 150,
                            }}>
                                <p style={{
                                    fontSize: '0.75rem', fontWeight: 700, color: '#64748b',
                                    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8
                                }}>
                                    {p.toUpperCase()}
                                </p>
                                <p style={{
                                    fontSize: '2rem', fontWeight: 800,
                                    color: val == null ? '#cbd5e1' : over ? '#e11d48' : '#059669'
                                }}>
                                    {val != null ? val.toFixed(1) : '—'}
                                </p>
                                <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 4 }}>
                                    Limit: {limit} μg/m³
                                </p>
                                {over && (
                                    <p style={{ fontSize: '0.75rem', color: '#e11d48', fontWeight: 600, marginTop: 4 }}>
                                        ↑ {((val / limit - 1) * 100).toFixed(0)}% over limit
                                    </p>
                                )}
                                {!over && val != null && (
                                    <p style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600, marginTop: 4 }}>
                                        ✓ Within limit
                                    </p>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* ── Section 4: 7-Day Violations Bar Chart ── */}
            <div className="card">
                <SectionTitle>Violations — Last 7 Days</SectionTitle>
                {chartData.length === 0 ? (
                    <p style={s.empty}>No data available</p>
                ) : (
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={chartData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                            <XAxis
                                dataKey="date"
                                tick={{ fontSize: 12, fill: '#94a3b8' }}
                                tickLine={false}
                                axisLine={false}
                            />
                            <YAxis
                                tick={{ fontSize: 12, fill: '#94a3b8' }}
                                tickLine={false}
                                axisLine={false}
                                allowDecimals={false}
                            />
                            <Tooltip
                                cursor={{ fill: '#f8fafc' }}
                                contentStyle={{
                                    background: '#fff', border: '1px solid #e2e8f0',
                                    borderRadius: 8, fontSize: 12
                                }}
                                formatter={(value) => [`${value} violations`, '']}
                            />
                            <Bar
                                dataKey="violations"
                                fill="#059669"
                                radius={[4, 4, 0, 0]}
                                maxBarSize={48}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                )}
            </div>
        </div>
    );
};

export default OverviewPage;
