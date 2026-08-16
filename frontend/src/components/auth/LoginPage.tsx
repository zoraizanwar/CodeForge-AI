import React, { useState } from 'react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    // Implementation
  };

  const handleGitHubLogin = async () => {
    const res = await fetch('/api/v1/auth/oauth/github/authorize?redirect_uri=' + window.location.origin + '/oauth/callback');
    const data = await res.json();
    window.location.href = data.url;
  };

  return (
    <div className="login-container">
      <h2>Login to CodeForge AI</h2>
      <form onSubmit={handleLogin}>
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" />
        <button type="submit">Login</button>
      </form>
      <button onClick={handleGitHubLogin}>Login with GitHub</button>
    </div>
  );
};
