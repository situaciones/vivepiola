import { createContext, useContext, useEffect, useState } from 'react';
import { jwtDecode } from 'jwt-decode';
import client from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  const cargarUsuario = async () => {
    const access = localStorage.getItem('access');
    if (!access) {
      setCargando(false);
      return;
    }
    try {
      const claims = jwtDecode(access);
      const { data } = await client.get('/auth/me/');
      setUsuario({ ...data, rol: claims.rol, condominio_id: claims.condominio_id, nombre_token: claims.nombre });
    } catch {
      localStorage.removeItem('access');
      localStorage.removeItem('refresh');
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarUsuario();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (username, password) => {
    const { data } = await client.post('/auth/login/', { username, password });
    localStorage.setItem('access', data.access);
    localStorage.setItem('refresh', data.refresh);
    await cargarUsuario();
  };

  const logout = () => {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    setUsuario(null);
  };

  return (
    <AuthContext.Provider value={{ usuario, login, logout, cargando }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
