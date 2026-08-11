import { useEffect, useRef, useState } from "react";
import { fetchNotifications, markNotificationRead, markAllNotificationsRead } from "../api.js";

const POLL_MS = 25000;

function timeAgo(iso) {
  const diffMin = Math.round((Date.now() - new Date(`${iso}Z`).getTime()) / 60000);
  if (diffMin < 1) return "gerade eben";
  if (diffMin < 60) return `vor ${diffMin} Min.`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `vor ${diffH} Std.`;
  return `vor ${Math.round(diffH / 24)} Tg.`;
}

// Polling in-app notification inbox (no websocket infra in this demo stack).
// Mounted once in the nav for any logged-in user, regardless of role — both
// Eltern and Tagespflegeperson accounts receive booking-related events.
export default function NotificationBell({ token }) {
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  function load() {
    fetchNotifications(token)
      .then((data) => {
        setItems(data.notifications);
        setUnreadCount(data.unread_count);
      })
      .catch(() => {});
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, [token]);

  useEffect(() => {
    function onClickOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function handleOpenItem(item) {
    if (!item.is_read) {
      setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
      markNotificationRead(token, item.id).catch(() => {});
    }
  }

  async function handleMarkAll() {
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
    markAllNotificationsRead(token).catch(() => {});
  }

  return (
    <div className="notif-wrap" ref={wrapRef}>
      <button
        type="button"
        className="notif-bell"
        onClick={() => setOpen((o) => !o)}
        aria-label="Benachrichtigungen"
      >
        🔔
        {unreadCount > 0 && <span className="notif-badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-head">
            <span>Benachrichtigungen</span>
            {unreadCount > 0 && (
              <button className="link-btn" onClick={handleMarkAll}>
                Alle als gelesen markieren
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="notif-empty">Noch keine Benachrichtigungen.</p>
          ) : (
            items.map((n) => (
              <button
                key={n.id}
                type="button"
                className={`notif-item ${n.is_read ? "" : "unread"}`}
                onClick={() => handleOpenItem(n)}
              >
                <span className={`notif-dot ${n.is_read ? "read" : ""}`} />
                <span className="notif-item-body">
                  <span className="notif-item-title">{n.title}</span>
                  <span className="notif-item-text">{n.body}</span>
                  <span className="notif-item-time">{timeAgo(n.created_at)}</span>
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
