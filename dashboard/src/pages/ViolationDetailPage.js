import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../services/api';

const ViolationDetailPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [event, setEvent] = useState(null);
    const [loading, setLoading] = useState(true);
    const [actionType, setActionType] = useState('ESCALATE');
    const [reason, setReason] = useState('');
    const [notes, setNotes] = useState('');
    const [busy, setBusy] = useState(false);
    const [reportLoading, setReportLoading] = useState(false);
    const [reportUrl, setReportUrl] = useState(null);

    useEffect(() => {
        fetchEvent();
    }, [id]);

    const fetchEvent = async () => {
        setLoading(true);
        try {
            const response = await api.get(`/api/violations/${id}`);
            setEvent(response.data);
        } catch (err) {
            console.error('Failed to fetch event', err);
        } finally {
            setLoading(false);
        }
    };

    const handleAction = async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
            await api.post('/api/actions/', {
                compliance_event_id: id,
                action_type: actionType,
                reason,
                notes
            });
            setReason('');
            setNotes('');
            fetchEvent(); // Refresh to show new action and status
        } catch (err) {
            alert('Failed to record action');
        } finally {
            setBusy(false);
        }
    };

    const handleGenerateReport = async () => {
        setReportLoading(true);
        try {
            // 1. Generate the report and get the report_id
            const genRes = await api.post(`/api/reports/generate/${id}`);
            const reportId = genRes.data.report_id;

            // 2. Fetch the HTML via authenticated request (avoids 401 from direct browser link)
            const htmlRes = await api.get(`/api/reports/${reportId}/html`, {
                responseType: 'blob',
            });

            // 3. Create a local Blob URL and open in new tab
            const blob = new Blob([htmlRes.data], { type: 'text/html' });
            const blobUrl = URL.createObjectURL(blob);
            setReportUrl(blobUrl);
            window.open(blobUrl, '_blank', 'noopener');
        } catch (err) {
            console.error('Report generation failed:', err);
            alert('Failed to generate report. See console for details.');
        } finally {
            setReportLoading(false);
        }
    };

    if (loading) return <div>Loading incident details...</div>;
    if (!event) return <div>Violation not found.</div>;

    return (
        <div style={{ maxWidth: '1000px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
                <div>
                    <button
                        onClick={() => navigate('/violations')}
                        style={{ background: 'none', color: 'var(--primary)', fontWeight: 600, marginBottom: '1rem', padding: 0 }}
                    >
                        ← Back to Violations
                    </button>
                    <h1 style={{ marginBottom: '0.5rem' }}>Violation Incident Details</h1>
                    <p style={{ color: 'var(--text-muted)' }}>ID: {event.id}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <span style={{
                        padding: '0.5rem 1rem',
                        borderRadius: '99px',
                        background: 'var(--tier-3)15',
                        color: 'var(--tier-3)',
                        fontWeight: 700,
                        fontSize: '0.875rem',
                        border: '1px solid var(--tier-3)30'
                    }}>
                        {event.tier}
                    </span>
                    <div style={{ marginTop: '1rem', fontWeight: 600, color: event.status === 'OPEN' ? '#b91c1c' : '#059669' }}>
                        ● Status: {event.status}
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '2rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    <div className="card">
                        <h3 style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Incident Evidence</h3>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                            <div>
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Station</p>
                                <p style={{ fontWeight: 500 }}>{event.station_id}</p>
                            </div>
                            <div>
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Pollutant</p>
                                <p style={{ fontWeight: 500 }}>{event.pollutant}</p>
                            </div>
                            <div>
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Observed Value</p>
                                <p style={{ fontWeight: 700, fontSize: '1.25rem', color: 'var(--tier-3)' }}>{event.observed_value.toFixed(2)}</p>
                            </div>
                            <div>
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>NAAQS Limit</p>
                                <p style={{ fontWeight: 500 }}>{event.limit_value} ({event.averaging_period})</p>
                            </div>
                        </div>
                        <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--bg-main)', borderRadius: '8px', border: '1px dashed var(--border)' }}>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>RULE INFORMATION</p>
                            <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}><strong>Rule:</strong> {event.rule_name}</p>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>{event.legal_reference}</p>
                        </div>
                    </div>

                    <div className="card">
                        <h3 style={{ marginBottom: '1rem' }}>Officer Action History</h3>
                        {event.officer_actions.length === 0 ? (
                            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No actions recorded yet.</p>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {event.officer_actions.map(action => (
                                    <div key={action.id} style={{ paddingLeft: '1rem', borderLeft: '3px solid var(--primary)', py: '0.25rem' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <p style={{ fontWeight: 600, fontSize: '0.875rem' }}>{action.action_type}</p>
                                            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{new Date(action.created_at).toLocaleString()}</p>
                                        </div>
                                        {action.reason && <p style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>{action.reason}</p>}
                                        {action.notes && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Note: {action.notes}</p>}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    <div className="card" style={{ border: '2px solid var(--primary)' }}>
                        <h3 style={{ marginBottom: '1.5rem' }}>Intervention Panel</h3>
                        <form onSubmit={handleAction}>
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem' }}>ACTION TYPE</label>
                                <select className="input-field" value={actionType} onChange={(e) => setActionType(e.target.value)}>
                                    <option value="ESCALATE">Escalate to Supervisor</option>
                                    <option value="DISMISS">Dismiss (False Positive)</option>
                                    <option value="FLAG_FOR_MONITORING">Flag for Monitoring</option>
                                </select>
                            </div>
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem' }}>REASON</label>
                                <input
                                    className="input-field"
                                    value={reason}
                                    onChange={(e) => setReason(e.target.value)}
                                    placeholder="Summary of decision..."
                                    required
                                />
                            </div>
                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem' }}>INTERNAL NOTES</label>
                                <textarea
                                    className="input-field"
                                    rows="3"
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    placeholder="Additional context for record..."
                                />
                            </div>
                            <button className="btn-primary" style={{ width: '100%' }} disabled={busy}>
                                {busy ? 'Processing...' : 'Record Action & Update Status'}
                            </button>
                        </form>
                    </div>

                    <div className="card">
                        <h3 style={{ marginBottom: '1rem' }}>Compliance Report</h3>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                            Standard regulatory report containing audit trail and station evidence.
                        </p>
                        <button
                            className="btn-primary"
                            style={{ width: '100%', background: 'white', color: 'var(--primary)', border: '1px solid var(--primary)' }}
                            onClick={handleGenerateReport}
                            disabled={reportLoading}
                        >
                            {reportLoading ? 'Generating...' : 'Regenerate HTML Report'}
                        </button>
                        {reportUrl && (
                            <a
                                href={reportUrl}
                                target="_blank"
                                rel="noreferrer"
                                style={{ display: 'block', textAlign: 'center', marginTop: '1rem', color: 'var(--primary)', fontWeight: 600, fontSize: '0.875rem' }}
                            >
                                View Report Link →
                            </a>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ViolationDetailPage;
