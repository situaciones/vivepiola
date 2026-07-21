import { LogOut, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useVocab } from '../vocab';

export default function AppShell({ tabs, active, onChange, dark = false, children }) {
  const { usuario, logout } = useAuth();
  const t = useVocab();
  const nombre = usuario?.first_name || usuario?.username || '';

  return (
    <div className={`app-shell${dark ? ' pagina-oscura' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo-mark"><ShieldCheck size={16} strokeWidth={2.4} /></span>
          VIVEPIOLA
        </div>

        <p className="sidebar-seccion-label">{usuario?.rol ? t(`rol_${usuario.rol}`) : ''}</p>
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
                {typeof tabItem.badge === 'number' && tabItem.badge > 0 && <span className="nav-badge">{tabItem.badge}</span>}
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

      <main className="app-content">{children}</main>
    </div>
  );
}
