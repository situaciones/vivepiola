import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

// Base para archivos servidos por Django (/media/...): evidencias, PDFs, CSVs.
export const MEDIA_BASE = API_URL.replace(/\/api\/?$/, '');

const client = axios.create({ baseURL: API_URL });

client.interceptors.request.use((config) => {
  const access = localStorage.getItem('access');
  if (access) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

let refrescando = null;

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem('refresh');
      if (!refresh) {
        return Promise.reject(error);
      }
      try {
        refrescando =
          refrescando ||
          axios.post(`${API_URL}/auth/refresh/`, { refresh }).then((res) => {
            localStorage.setItem('access', res.data.access);
            return res.data.access;
          });
        const nuevoAccess = await refrescando;
        refrescando = null;
        original.headers.Authorization = `Bearer ${nuevoAccess}`;
        return client(original);
      } catch (refreshError) {
        localStorage.removeItem('access');
        localStorage.removeItem('refresh');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  },
);

export default client;
