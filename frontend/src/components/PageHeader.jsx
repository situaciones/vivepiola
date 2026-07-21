export default function PageHeader({ titulo, subtitulo, stats = [] }) {
  return (
    <div className="page-header">
      <h1>{titulo}</h1>
      {subtitulo && <p className="subtitulo">{subtitulo}</p>}
      {stats.length > 0 && (
        <div className="stats-grid">
          {stats.map((s) => (
            <div key={s.label} className={`stat-card${s.alerta ? ' alerta' : ''}`}>
              <div className="stat-valor">{s.valor}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
