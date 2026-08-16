import React, { useEffect, useState } from 'react';
import type { ExternalIdentity } from '../../services/auth';
import { fetchIdentities, unlinkIdentity } from '../../services/auth';

export const ConnectedIdentities: React.FC = () => {
  const [identities, setIdentities] = useState<ExternalIdentity[]>([]);

  useEffect(() => {
    fetchIdentities().then(setIdentities).catch(console.error);
  }, []);

  const handleUnlink = async (id: string) => {
    await unlinkIdentity(id);
    setIdentities(idents => idents.filter(x => x.id !== id));
  };

  return (
    <div>
      <h3>Connected Identities</h3>
      <ul>
        {identities.map(i => (
          <li key={i.id}>
            {i.provider}: {i.provider_email || i.provider_username || i.provider_subject}
            <button onClick={() => handleUnlink(i.id)}>Unlink</button>
          </li>
        ))}
      </ul>
    </div>
  );
};
