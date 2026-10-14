import { useEffect, useState } from "react"
import AnswerCard from "./AnswerCard"
import ChatDesk from "./ChatDesk"
import DocumentDesk from "./DocumentDesk"
import OrgTree from "./OrgTree"
import { post, remove, request } from "./api"

const CONTRACTS = {
  full_time: "nhân viên chính thức",
  intern: "thực tập sinh",
  contractor: "cộng tác viên",
}

function personaLabel(persona) {
  const contract = CONTRACTS[persona.employment_type] || persona.employment_type
  return `${persona.name} · ${persona.org_path} · ${contract}`
}

export default function App() {
  const [view, setView] = useState("ask")
  const [personas, setPersonas] = useState([])
  const [catalog, setCatalog] = useState(null)
  const [documents, setDocuments] = useState([])
  const [orgTree, setOrgTree] = useState(null)
  const [leftId, setLeftId] = useState("lan")
  const [rightId, setRightId] = useState("minh")
  const [question, setQuestion] = useState("Quy định nghỉ phép của tôi như thế nào?")
  const [asOf, setAsOf] = useState("2026-10-08")
  const [left, setLeft] = useState(null)
  const [right, setRight] = useState(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [focusId, setFocusId] = useState(null)

  async function deleteDocument(versionId) {
    await remove(`/api/documents/${encodeURIComponent(versionId)}`)
    if (focusId === versionId) setFocusId(null)
    await loadDocuments()
  }

  async function loadDocuments() {
    const [docs, tree] = await Promise.all([
      request("/api/documents"),
      request("/api/org-tree"),
    ])
    setDocuments(docs)
    setOrgTree(tree)
  }

  async function runCompare(next) {
    const payload = {
      leftId: next.leftId ?? leftId,
      rightId: next.rightId ?? rightId,
      question: next.question ?? question,
      asOf: next.asOf ?? asOf,
    }
    setLeftId(payload.leftId)
    setRightId(payload.rightId)
    setQuestion(payload.question)
    setAsOf(payload.asOf)
    setBusy(true)
    setError("")
    try {
      const result = await post("/api/compare", {
        left_id: payload.leftId,
        right_id: payload.rightId,
        question: payload.question,
        as_of: payload.asOf,
      })
      setLeft(result.left)
      setRight(result.right)
    } catch (caught) {
      setLeft(null)
      setRight(null)
      setError(caught.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    Promise.all([request("/api/personas"), request("/api/catalog"), request("/api/documents"), request("/api/org-tree")])
      .then(([people, options, docs, tree]) => {
        setPersonas(people)
        setCatalog(options)
        setDocuments(docs)
        setOrgTree(tree)
        return runCompare({ leftId: "lan", rightId: "minh" })
      })
      .catch((caught) => setError(caught.message || "Chưa tải được dữ liệu."))
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="mark">A</div>
          <div>
            <p className="eyebrow">Tri thức có phân quyền</p>
            <h1>Appota_leave-demo</h1>
          </div>
        </div>
        <nav className="tabs">
          <button className={view === "ask" ? "active" : ""} type="button" onClick={() => setView("ask")}>Tìm kiếm</button>
          <button className={view === "chat" ? "active" : ""} type="button" onClick={() => setView("chat")}>Hỏi đáp</button>
          <button className={view === "docs" ? "active" : ""} type="button" onClick={() => setView("docs")}>Tài liệu</button>
          <button className={view === "tree" ? "active" : ""} type="button" onClick={() => setView("tree")}>Cây tổ chức</button>
        </nav>
      </header>

      {view === "ask" ? (
        <main className="shell">
          <form className="panel" onSubmit={(event) => { event.preventDefault(); runCompare({}) }}>
            <label>Người bên trái
              <select value={leftId} onChange={(event) => setLeftId(event.target.value)}>
                {personas.map((persona) => <option key={persona.id} value={persona.id}>{personaLabel(persona)}</option>)}
              </select>
            </label>
            <label>Người bên phải
              <select value={rightId} onChange={(event) => setRightId(event.target.value)}>
                {personas.map((persona) => <option key={persona.id} value={persona.id}>{personaLabel(persona)}</option>)}
              </select>
            </label>
            <label>Ngày hỏi
              <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
            </label>
            <label>Câu hỏi
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
            </label>
            <div className="actions">
              <button className="primary" type="submit" disabled={busy}>{busy ? "Đang tìm kiếm..." : "Tìm kiếm"}</button>
            </div>
          </form>
          <section className="results">
            {error ? <p className="banner error">{error}</p> : null}
            {left && right && left.as_of !== right.as_of ? (
              <p className="banner">Cùng một người, hai ngày hiệu lực: {left.as_of} và {right.as_of}.</p>
            ) : null}
            {left && right ? (
              <>
                <AnswerCard result={left} onOpen={(versionId) => { setFocusId(versionId); setView("docs") }} />
                <AnswerCard result={right} onOpen={(versionId) => { setFocusId(versionId); setView("docs") }} />
              </>
            ) : !error ? <div className="empty">Đang lấy câu trả lời...</div> : null}
          </section>
        </main>
      ) : view === "chat" ? (
        <ChatDesk personas={personas} onOpen={(versionId) => { setFocusId(versionId); setView("docs") }} />
      ) : view === "tree" ? (
        orgTree ? <OrgTree tree={orgTree} onOpen={(versionId) => { setFocusId(versionId); setView("docs") }} onDelete={deleteDocument} /> : <p className="banner error">Chưa tải được cây tổ chức.</p>
      ) : catalog ? (
        <DocumentDesk catalog={catalog} documents={documents} onSaved={loadDocuments} focusId={focusId} />
      ) : <p className="banner error">Chưa tải được danh mục tài liệu.</p>}
    </div>
  )
}
