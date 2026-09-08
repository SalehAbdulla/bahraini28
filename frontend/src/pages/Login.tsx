import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { RequestError } from "../api/client";

export default function Login() {
  const { login, activateProfile } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ??
    "/profile";

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [showActivate, setShowActivate] = useState(false);
  const [actName, setActName] = useState("");
  const [actEmail, setActEmail] = useState("");
  const [actPassword, setActPassword] = useState("");
  const [actError, setActError] = useState("");
  const [actBusy, setActBusy] = useState(false);

  const submitLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const mustChange = await login(identifier, password);
      if (mustChange) {
        setShowActivate(true);
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  const submitActivate = async (e: FormEvent) => {
    e.preventDefault();
    setActError("");
    setActBusy(true);
    try {
      await activateProfile(actName, actEmail, actPassword);
      navigate("/profile", { replace: true });
    } catch (err) {
      setActError(err instanceof RequestError ? err.message : "Activation failed.");
    } finally {
      setActBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-8">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-8">
        <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-500">
          Login with your email or CPR number.
        </p>
        <div className="mt-4 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          🔒 Volunteer Members Only — access is validated against your
          membership expiry date.
        </div>
        <form onSubmit={submitLogin} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="identifier" className="block text-sm font-medium text-slate-700">
              Email or CPR
            </label>
            <input
              id="identifier"
              type="text"
              required
              autoComplete="username"
              className="input-field"
              placeholder="you@example.com or CPR number"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              className="input-field"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
      {showActivate && (
        <ActivationModal
          actName={actName} setActName={setActName}
          actEmail={actEmail} setActEmail={setActEmail}
          actPassword={actPassword} setActPassword={setActPassword}
          actError={actError} actBusy={actBusy}
          onSubmit={submitActivate}
        />
      )}
    </div>
  );
}

interface ActivationModalProps {
  actName: string;
  setActName: (v: string) => void;
  actEmail: string;
  setActEmail: (v: string) => void;
  actPassword: string;
  setActPassword: (v: string) => void;
  actError: string;
  actBusy: boolean;
  onSubmit: (e: FormEvent) => Promise<void>;
}

function ActivationModal(props: ActivationModalProps) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 grid place-items-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8 max-w-md w-full">
        <h2 className="text-xl font-bold text-slate-900">Set up your profile</h2>
        <p className="mt-1 text-sm text-slate-500">
          For security, please update your name, email and password to continue.
        </p>
        <form onSubmit={props.onSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label className="block text-sm font-medium text-slate-700">Full name</label>
            <input
              className="input-field"
              required
              minLength={2}
              value={props.actName}
              onChange={(e) => props.setActName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Email address</label>
            <input
              type="email"
              className="input-field"
              required
              value={props.actEmail}
              onChange={(e) => props.setActEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">New password</label>
            <input
              type="password"
              className="input-field"
              required
              minLength={8}
              maxLength={72}
              value={props.actPassword}
              onChange={(e) => props.setActPassword(e.target.value)}
            />
          </div>
          {props.actError && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {props.actError}
            </div>
          )}
          <button type="submit" disabled={props.actBusy} className="btn-primary w-full">
            {props.actBusy ? "Saving…" : "Save & continue"}
          </button>
        </form>
      </div>
    </div>
  );
}