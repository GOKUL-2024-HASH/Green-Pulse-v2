import axios from 'axios';

// In production (Render), point to the deployed API service.
// In local Docker dev, leave empty so nginx reverse-proxies /api/* correctly.
const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://greenpulse-api.onrender.com';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor for API calls
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor for handling token expiration
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Auto logout on 401
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default api;
