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

  async function submit(event) {
    event.preventDefault()
    const text = question.trim()
    if (!text) return
    setBusy(true)
    setError("")
    try {
      const result = await post("/api/chat", {
        persona_id: personaId,
        question: text,
        as_of: asOf,
      })
      setTurns((current) => [...current, result])
      setQuestion("")
    } catch (caught) {
      setError(caught.message)
    } finally {
      setBusy(false)
    }
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
            <p className="kicker">{turn.persona.name} · ngày {turn.as_of}</p>
            <h2 className="who">{turn.question}</h2>
            <p className="answer">{turn.answer}</p>
            <p className="reason">{turn.reason}</p>
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
