"use client";

import { useAuth } from "@/lib/auth";

export function UserMenu() {
  const { user, signOut } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <div className="user-menu" role="group" aria-label="Account">
      <div className="user-menu-identity">
        {user.picture ? (
          // eslint-disable-next-line @next/next/no-img-element -- Google profile URL; avoid next/image remote config
          <img
            className="user-menu-avatar"
            src={user.picture}
            alt=""
            width={32}
            height={32}
            referrerPolicy="no-referrer"
          />
        ) : null}
        <div className="user-menu-text">
          <span className="user-menu-name">{user.name}</span>
          <span className="user-menu-email">{user.email}</span>
        </div>
      </div>
      <button
        type="button"
        className="sign-out-button"
        onClick={() => signOut()}
        aria-label={`Sign out ${user.name}`}
      >
        Sign out
      </button>
    </div>
  );
}
