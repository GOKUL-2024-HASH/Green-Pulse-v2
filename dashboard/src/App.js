import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import './index.css';

// Components
import Sidebar from './components/Sidebar';

// Pages
import LoginPage from './pages/LoginPage';
import OverviewPage from './pages/OverviewPage';
import ViolationsPage from './pages/ViolationsPage';
import StationsPage from './pages/StationsPage';
import ViolationDetailPage from './pages/ViolationDetailPage';

const ProtectedLayout = ({ children }) => {
    const { user, loading } = useAuth();

    if (loading) return <div>Loading...</div>;
    if (!user) return <Navigate to="/login" />;

    return (
        <div style={{ display: 'flex' }}>
            <Sidebar />
            <main style={{ marginLeft: '260px', flex: 1, padding: '2.5rem', minHeight: '100vh' }}>
                {children}
            </main>
        </div>
    );
};

function App() {
    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />

                    <Route path="/" element={
                        <ProtectedLayout>
                            <OverviewPage />
                        </ProtectedLayout>
                    } />

                    <Route path="/violations" element={
                        <ProtectedLayout>
                            <ViolationsPage />
                        </ProtectedLayout>
                    } />

                    <Route path="/violations/:id" element={
                        <ProtectedLayout>
                            <ViolationDetailPage />
                        </ProtectedLayout>
                    } />

                    <Route path="/stations" element={
                        <ProtectedLayout>
                            <StationsPage />
                        </ProtectedLayout>
                    } />

                    <Route path="*" element={<Navigate to="/" />} />
                </Routes>
            </Router>
        </AuthProvider>
    );
}

export default App;
