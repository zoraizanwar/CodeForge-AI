import React, { useEffect, useState } from 'react';
import type { ActiveSession } from '../../services/auth';
import { fetchSessions, revokeSession } from '../../services/auth';

export const ActiveSessions: React.FC = () => {
  const [sessions, setSessions] = useState<ActiveSession[]>([]);

  useEffect(() => {
    fetchSessions().then(setSessions).catch(console.error);
  }, []);

  const handleRevoke = async (id: string) => {
    await revokeSession(id);
    setSessions(s => s.filter(x => x.id !== id));
  };

  return (
    <div>
      <h3>Active Sessions</h3>
      <ul>
        {sessions.map(s => (
          <li key={s.id}>
            Started: {s.created_at} - Expires: {s.expires_at}
            <button onClick={() => handleRevoke(s.id)}>Revoke</button>
          </li>
        ))}
      </ul>
    </div>
  );
};
