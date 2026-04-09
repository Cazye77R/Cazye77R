// Activity log panel — shows agent events
export default function ActivityLog({ entries = [] }) {
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 12, padding: 8 }}>
      <strong>Activity Log</strong>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {entries.map((e, i) => (
          <li key={i}>[{e.time}] {e.agent}: {e.message}</li>
        ))}
      </ul>
    </div>
  );
}
