import { useEffect, useState } from 'react';
import { App as AppNativa } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { LayoutGrid, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useVocab } from '../vocab';
import Marca from './Marca';

// La navegacion inferior del telefono admite cinco destinos comodos para el
// pulgar; si hay mas, los ultimos se agrupan en "Mas".
const MAX_NAV_INFERIOR = 5;

function Badge({ valor }) {
  return typeof valor === 'number' && valor > 0 ? <span className="nav-badge">{valor > 99 ? '99+' : valor}</span> : null;
}

export default function AppShell({ tabs, active, onChange, dark = false, children }) {
  const { usuario, logout } = useAuth();
  const t = useVocab();
  const nombre = usuario?.first_name || usuario?.username || '';
  const rol = usuario?.rol ? t(`rol_${usuario.rol}`) : '';
  // null = cerrada; 'perfil' o 'mas' = que muestra la hoja inferior.
  const [hoja, setHoja] = useState(null);

  const desbordan = tabs.length > MAX_NAV_INFERIOR;
  const visibles = desbordan ? tabs.slice(0, MAX_NAV_INFERIOR - 1) : tabs;
  const resto = desbordan ? tabs.slice(MAX_NAV_INFERIOR - 1) : [];
  const activoEnResto = resto.some((tabItem) => tabItem.id === active);
  const badgeResto = resto.reduce((suma, tabItem) => suma + (tabItem.badge || 0), 0);

  // Boton atras de Android: primero cierra la hoja, despues vuelve a la
  // seccion principal y solo entonces deja la app en segundo plano. Sin esto,
  // un toque de mas cerraba la app en medio de un caso.
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return undefined;
    const escucha = AppNativa.addListener('backButton', () => {
      if (hoja) setHoja(null);
      else if (tabs.length && active !== tabs[0].id) onChange(tabs[0].id);
      else AppNativa.minimizeApp();
    });
    return () => {
      escucha.then((e) => e.remove());
    };
  }, [hoja, active, tabs, onChange]);

  const elegir = (id) => {
    setHoja(null);
    onChange(id);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className={`app-shell${dark ? ' pagina-oscura' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Marca size={30} />
        </div>

        <p className="sidebar-seccion-label">{rol}</p>
        <nav className="sidebar-nav">
          {tabs.map((tabItem) => {
            const Icon = tabItem.icon;
            return (
              <button
                key={tabItem.id}
                type="button"
                className={`sidebar-link${active === tabItem.id ? ' activo' : ''}`}
                onClick={() => onChange(tabItem.id)}
              >
                <Icon size={17} strokeWidth={2} />
                {tabItem.label}
                <Badge valor={tabItem.badge} />
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <span className="avatar">{nombre.slice(0, 2)}</span>
          <div className="sidebar-footer-info">
            <div className="sidebar-footer-nombre">{nombre}</div>
            <div className="sidebar-footer-rol">{usuario?.username}</div>
          </div>
          <button className="btn-icono" onClick={logout} title="Cerrar sesion" aria-label="Cerrar sesion">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <header className="barra-app">
        <Marca size={30} />
        <button type="button" className="barra-perfil" onClick={() => setHoja('perfil')} aria-label="Abrir perfil">
          {rol}
          <span className="avatar">{nombre.slice(0, 2)}</span>
        </button>
      </header>

      <main className="app-content">{children}</main>

      <nav className="nav-inferior" aria-label="Secciones">
        {visibles.map((tabItem) => {
          const Icon = tabItem.icon;
          return (
            <button
              key={tabItem.id}
              type="button"
              className={`nav-item${active === tabItem.id ? ' activo' : ''}`}
              onClick={() => elegir(tabItem.id)}
              aria-current={active === tabItem.id ? 'page' : undefined}
            >
              <span className="nav-item-icono">
                <Icon size={20} strokeWidth={2} />
                <Badge valor={tabItem.badge} />
              </span>
              <span className="nav-item-texto">{tabItem.corto || tabItem.label}</span>
            </button>
          );
        })}
        {desbordan && (
          <button type="button" className={`nav-item${activoEnResto ? ' activo' : ''}`} onClick={() => setHoja('mas')}>
            <span className="nav-item-icono">
              <LayoutGrid size={20} strokeWidth={2} />
              <Badge valor={badgeResto} />
            </span>
            <span className="nav-item-texto">Mas</span>
          </button>
        )}
      </nav>

      {hoja && (
        <div className="hoja-overlay" onClick={() => setHoja(null)}>
          <div className="hoja" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="hoja-asa" />
            {hoja === 'perfil' ? (
              <>
                <div className="hoja-perfil">
                  <span className="avatar">{nombre.slice(0, 2)}</span>
                  <div>
                    <strong>{nombre}</strong>
                    <span>{rol} · {usuario?.username}</span>
                  </div>
                </div>
                <button type="button" className="hoja-opcion peligro" onClick={logout}>
                  <LogOut size={20} /> Cerrar sesion
                </button>
              </>
            ) : (
              <>
              <p className="hoja-titulo">Mas secciones</p>
              {resto.map((tabItem) => {
                const Icon = tabItem.icon;
                return (
                  <button
                    key={tabItem.id}
                    type="button"
                    className={`hoja-opcion${active === tabItem.id ? ' activo' : ''}`}
                    onClick={() => elegir(tabItem.id)}
                  >
                    <Icon size={20} />
                    {tabItem.label}
                    <Badge valor={tabItem.badge} />
                  </button>
                );
              })}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
