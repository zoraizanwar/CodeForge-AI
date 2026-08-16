import React from 'react';
import { ActiveSessions } from './ActiveSessions';
import { ConnectedIdentities } from './ConnectedIdentities';

export const AccountSecurity: React.FC = () => {
  return (
    <div>
      <h2>Account Security</h2>
      <ConnectedIdentities />
      <ActiveSessions />
    </div>
  );
};
