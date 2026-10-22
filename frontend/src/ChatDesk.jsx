import { useState } from "react"
import { post } from "./api"

const CONTRACTS = {
  full_time: "nhân viên chính thức",
  intern: "thực tập sinh",
  contractor: "cộng tác viên",
}

const CLEARANCE = {
  internal: "nội bộ",
  confidential: "mật",
  restricted: "hạn chế",
}

const OUTCOMES = {
  answered: "Đã chọn quy định",
  conflict: "Xung đột",
  no_policy: "Không đủ căn cứ",
  unknown_topic: "Ngoài chủ đề",
}

const ROLES = {
  employee: "nhân viên",
  intern: "thực tập",
  manager: "quản lý",
  policy_admin: "quản trị chính sách",
  contractor: "cộng tác viên",
}

function formatDay(value) {
  if (!value) return ""
  const [year, month, day] = value.split("-")
  return `${day}/${month}/${year}`
}

function personaLabel(persona) {
  const contract = CONTRACTS[persona.employment_type] || persona.employment_type
  const clearance = CLEARANCE[persona.clearance] || persona.clearance
  return `${persona.name} · ${persona.org_path} · ${contract} · ${clearance}`
}

export default function ChatDesk({ personas, onOpen }) {
  const [personaId, setPersonaId] = useState("lan")
  const [asOf, setAsOf] = useState("2026-10-08")
  const [question, setQuestion] = useState("")
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function ask(id, text, day) {
    setBusy(true)
    setError("")
    setPersonaId(id)
    setAsOf(day)
    setQuestion(text)
    try {
      const result = await post("/api/chat", {
        persona_id: id,
        question: text,
        as_of: day,
      })
      setTurns((current) => [...current, result])
      setQuestion("")
    } catch (caught) {
      setError(caught.message)
    } finally {
      setBusy(false)
    }
  }

  async function submit(event) {
    event.preventDefault()
    const text = question.trim()
    if (!text) return
    await ask(personaId, text, asOf)
  }

  return (
    <main className="shell">
      <form className="panel" onSubmit={submit}>
        <p className="lede">Agent gắn đúng người hỏi, lọc quyền, lấy đoạn tài liệu liên quan, rồi mới viết câu trả lời.</p>
        <label>Người hỏi
          <select value={personaId} onChange={(event) => { setPersonaId(event.target.value); setTurns([]) }}>
            {personas.map((persona) => <option key={persona.id} value={persona.id}>{personaLabel(persona)}</option>)}
          </select>
        </label>
        <label>Ngày hỏi
          <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
        </label>
        <label>Câu hỏi
          <textarea value={question} placeholder="Ví dụ: Ca kíp được nghỉ thêm thế nào?" onChange={(event) => setQuestion(event.target.value)} />
        </label>
        <div className="actions">
          <button className="primary" type="submit" disabled={busy || !question.trim()}>{busy ? "Đang trả lời..." : "Hỏi"}</button>
        </div>
        {error ? <p className="banner error">{error}</p> : null}
      </form>
      <section className="thread">
        {turns.length === 0 ? <div className="empty">Câu trả lời sẽ hiện ở đây.</div> : turns.map((turn, index) => (
          <article className={`card ${turn.outcome}`} key={`${turn.question}-${index}`}>
            <div className="card-head">
              <div>
                <p className="kicker">{turn.persona.name} · ngày {formatDay(turn.as_of)}</p>
                <p className="lede">
                  {turn.persona.org_path}
                  {" · "}
                  {(turn.persona.roles || []).map((role) => ROLES[role] || role).join(", ")}
                  {" · "}
                  {CONTRACTS[turn.persona.employment_type] || turn.persona.employment_type}
                  {" · mức "}
                  {CLEARANCE[turn.persona.clearance] || turn.persona.clearance}
                </p>
                <h2 className="who">{turn.question}</h2>
              </div>
              <span className="pill">{OUTCOMES[turn.outcome] || turn.outcome}</span>
            </div>
            <p className="answer">{turn.answer}</p>
            {turn.reason && turn.reason !== turn.answer ? <p className="reason">{turn.reason}</p> : null}
            {turn.sources.length > 0 ? (
              <div className="source">
                <p className="kicker">Tài liệu dùng</p>
                <div className="actions">
                  {turn.sources.map((source) => (
                    <button
                      className="text-link"
                      type="button"
                      key={`${source.document_id}-${source.version}`}
                      onClick={() => onOpen(`${source.document_id}-v${source.version}`, turn.persona.id)}
                    >
                      {source.document_id} v{source.version}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </main>
  )
}
