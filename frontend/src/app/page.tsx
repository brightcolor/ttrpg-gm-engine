"use client";

import { useEffect, useMemo, useState } from "react";
import { BookOpen, Bot, Dices, Moon, RefreshCw, Send, Settings, Shield, Sun, Users } from "lucide-react";
import { API_URL, Campaign, Overview, api } from "@/lib/api";

type ChatMessage = { sender: "player" | "gm"; text: string };

export default function Home() {
  const [theme, setTheme] = useState("dark");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [overview, setOverview] = useState<Overview>({ characters: [], npcs: [], quests: [] });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("Ich betrete die Schmiede und frage Alrik nach den Lichtern in der alten Muehle.");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"player" | "admin" | "rules">("player");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  async function loadCampaigns() {
    const data = await api<Campaign[]>("/api/campaigns");
    setCampaigns(data);
    if (!campaignId && data[0]) setCampaignId(data[0].id);
  }

  async function seed() {
    await api("/api/seed", { method: "POST", body: "{}" });
    await loadCampaigns();
  }

  useEffect(() => {
    loadCampaigns().catch(() => seed());
  }, []);

  useEffect(() => {
    if (!campaignId) return;
    api<Overview>(`/api/campaigns/${campaignId}/overview`).then(setOverview).catch(console.error);
  }, [campaignId]);

  const campaign = useMemo(() => campaigns.find((c) => c.id === campaignId), [campaigns, campaignId]);

  async function send() {
    if (!input.trim() || !campaignId) return;
    const playerText = input;
    setMessages((old) => [...old, { sender: "player", text: playerText }]);
    setInput("");
    setBusy(true);
    try {
      const result = await api<{ text: string; session_id: string }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ campaign_id: campaignId, session_id: sessionId, message: playerText })
      });
      setSessionId(result.session_id);
      setMessages((old) => [...old, { sender: "gm", text: result.text }]);
      await api<Overview>(`/api/campaigns/${campaignId}/overview`).then(setOverview);
    } finally {
      setBusy(false);
    }
  }

  async function roll() {
    if (!campaignId) return;
    const result = await api<any>("/api/tools/run", {
      method: "POST",
      body: JSON.stringify({ campaign_id: campaignId, session_id: sessionId, tool_name: "roll_dice", input: { expression: "1d20+3", reason: "Manual UI roll", visibility: "public" } })
    });
    setMessages((old) => [...old, { sender: "gm", text: `Wuerfelwurf 1d20+3: ${result.result.total}` }]);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">TTRPG GM Engine</div>
        <p className="small muted">Systemagnostische Kampagnen-Engine mit Tool-Audit, Rulesets und persistentem Memory.</p>
        <div className="section-title">Kampagnen</div>
        <div className="stack">
          {campaigns.map((item) => (
            <button key={item.id} className={item.id === campaignId ? "card active" : "card"} onClick={() => setCampaignId(item.id)}>
              <strong>{item.name}</strong>
              <div className="small muted">{item.mode}</div>
            </button>
          ))}
          <button onClick={seed}><RefreshCw size={16} /> Demo laden</button>
        </div>
        <div className="section-title">Modus</div>
        <div className="tabs">
          <button className={tab === "player" ? "tab-active" : ""} onClick={() => setTab("player")} title="Spieleransicht"><Users size={16} /></button>
          <button className={tab === "admin" ? "tab-active" : ""} onClick={() => setTab("admin")} title="Admin"><Settings size={16} /></button>
          <button className={tab === "rules" ? "tab-active" : ""} onClick={() => setTab("rules")} title="Rulesets"><Shield size={16} /></button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <strong>{campaign?.name || "Keine Kampagne"}</strong>
            <div className="small muted">{campaign?.description}</div>
          </div>
          <div className="tabs">
            <button onClick={roll} title="Wuerfeln"><Dices size={17} /></button>
            <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Theme wechseln">{theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}</button>
          </div>
        </header>
        <section className="chat">
          {messages.length === 0 && (
            <div className="message">
              <strong>Aktuelle Szene</strong>
              <p>{String(campaign?.current_scene?.summary || "Lade eine Demo-Kampagne oder lege eine neue Kampagne an.")}</p>
              <span className="small muted">Backend: {API_URL}</span>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.sender}`}>
              <strong>{message.sender === "player" ? "Spieler" : "GM"}</strong>
              <div>{message.text}</div>
            </div>
          ))}
        </section>
        <footer className="composer">
          <textarea rows={3} value={input} onChange={(event) => setInput(event.target.value)} />
          <button onClick={send} disabled={busy} className="primary" title="Senden"><Send size={17} /> {busy ? "..." : "Senden"}</button>
          <button onClick={roll} title="Wuerfeln"><Dices size={17} /></button>
        </footer>
      </main>

      <aside className="rightbar">
        {tab === "player" && <PlayerPanel overview={overview} />}
        {tab === "admin" && <AdminPanel overview={overview} />}
        {tab === "rules" && <RulesPanel />}
      </aside>
    </div>
  );
}

function PlayerPanel({ overview }: { overview: Overview }) {
  return (
    <div>
      <div className="section-title">Charaktere</div>
      <div className="stack">{overview.characters.map((c) => <EntityCard key={c.id} icon={<Users size={16} />} title={c.name} body={c.summary} data={c.ruleset_data} />)}</div>
      <div className="section-title">Aktive Quests</div>
      <div className="stack">{overview.quests.map((q) => <EntityCard key={q.id} icon={<BookOpen size={16} />} title={q.title} body={q.description} data={{ status: q.status, stakes: q.stakes }} />)}</div>
    </div>
  );
}

function AdminPanel({ overview }: { overview: Overview }) {
  return (
    <div>
      <div className="section-title">NPCs</div>
      <div className="stack">{overview.npcs.map((n) => <EntityCard key={n.id} icon={<Bot size={16} />} title={n.name} body={`${n.role} · ${n.summary}`} data={{ public: n.public_data, gm: n.gm_data }} />)}</div>
      <div className="section-title">Audit & Import</div>
      <div className="card small">Tool-Aufrufe, Lore-Import und LLM-Requests sind im Backend persistent auditierbar. Der MVP stellt die Daten bereits ueber die API bereit; detaillierte Tabellenansicht ist fuer die naechste UI-Iteration vorbereitet.</div>
    </div>
  );
}

function RulesPanel() {
  const [rulesets, setRulesets] = useState<Array<Record<string, any>>>([]);
  useEffect(() => {
    api<Array<Record<string, any>>>("/api/rulesets").then(setRulesets).catch(console.error);
  }, []);
  return (
    <div>
      <div className="section-title">Rulesets</div>
      <div className="stack">
        {rulesets.map((r) => (
          <div className="card" key={r.id}>
            <strong>{r.name}</strong>
            <div className="small muted">{r.slug}</div>
            <p className="small">{r.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function EntityCard({ icon, title, body, data }: { icon: React.ReactNode; title: string; body?: string; data?: Record<string, any> }) {
  return (
    <div className="card">
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>{icon}<strong>{title}</strong></div>
      {body && <p className="small">{body}</p>}
      {data && <pre className="small muted" style={{ whiteSpace: "pre-wrap", overflow: "auto", maxHeight: 180 }}>{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}

