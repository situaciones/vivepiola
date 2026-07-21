import { Inbox } from 'lucide-react';

export default function EmptyState({ icon: Icon = Inbox, mensaje }) {
  return (
    <div className="estado-vacio">
      <Icon size={22} strokeWidth={1.6} />
      {mensaje}
    </div>
  );
}
