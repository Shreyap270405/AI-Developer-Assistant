import React, { useState } from 'react';

/**
 * AuthLayout wraps authentication pages (login / register) and provides
 * a toggle between the two forms without routing.
 */
export default function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      {children}
    </div>
  );
}
