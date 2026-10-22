import { useEffect, useState } from "react"
import logo from "./assets/logo.png"
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

const CLEARANCE = {
  internal: "nội bộ",
  confidential: "mật",
  restricted: "hạn chế",
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
  const [leftAsOf, setLeftAsOf] = useState("2026-10-08")
  const [rightAsOf, setRightAsOf] = useState("2026-10-08")
  const [left, setLeft] = useState(null)
  const [right, setRight] = useState(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [focusId, setFocusId] = useState(null)
  const [citation, setCitation] = useState(null)
  const [libraryId, setLibraryId] = useState("lan")

  const libraryPersona = personas.find((persona) => persona.id === libraryId)
  const canManage = Boolean(libraryPersona?.roles.includes("policy_admin"))

  function libraryQuery(personaId = libraryId, on = asOf) {
    return new URLSearchParams({ persona_id: personaId, as_of: on }).toString()
  }

  function openLibrary(versionId, personaId, nextCitation = null) {
    setLibraryId(personaId)
    setFocusId(versionId)
    setCitation(nextCitation ? { ...nextCitation, versionId } : null)
    setView("docs")
    loadDocuments(personaId, asOf)
  }

  async function deleteDocument(versionId) {
    const params = new URLSearchParams({ persona_id: libraryId })
    await remove(`/api/documents/${encodeURIComponent(versionId)}?${params}`)
    if (focusId === versionId) setFocusId(null)
    await loadDocuments()
  }

  async function loadDocuments(personaId = libraryId, on = asOf) {
    const query = libraryQuery(personaId, on)
    const [docs, tree] = await Promise.all([
      request(`/api/documents?${query}`),
      request(`/api/org-tree?${query}`),
    ])
    setDocuments(docs)
    setOrgTree(tree)
  }

  async function runCompare(next) {
    const payload = {
      leftId: next.leftId ?? leftId,
      rightId: next.rightId ?? rightId,
      question: next.question ?? question,
      leftAsOf: next.leftAsOf ?? leftAsOf,
      rightAsOf: next.rightAsOf ?? rightAsOf,
    }
    setLeftId(payload.leftId)
    setRightId(payload.rightId)
    setQuestion(payload.question)
    setLeftAsOf(payload.leftAsOf)
    setRightAsOf(payload.rightAsOf)
    setAsOf(payload.leftAsOf)
    setBusy(true)
    setError("")
    try {
      const result = await post("/api/compare", {
        left_id: payload.leftId,
        right_id: payload.rightId,
        question: payload.question,
        as_of: payload.leftAsOf,
        left_as_of: payload.leftAsOf,
        right_as_of: payload.rightAsOf,
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
    const query = new URLSearchParams({ persona_id: "lan", as_of: "2026-10-08" }).toString()
    Promise.all([
      request("/api/personas"),
      request("/api/catalog"),
      request(`/api/documents?${query}`),
      request(`/api/org-tree?${query}`),
    ])
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
          <img className="logo" src={logo} alt="Appota" />
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
            <label>Ngày hỏi bên trái
              <input type="date" value={leftAsOf} onChange={(event) => setLeftAsOf(event.target.value)} />
            </label>
            <label>Người bên phải
              <select value={rightId} onChange={(event) => setRightId(event.target.value)}>
                {personas.map((persona) => <option key={persona.id} value={persona.id}>{personaLabel(persona)}</option>)}
              </select>
            </label>
            <label>Ngày hỏi bên phải
              <input type="date" value={rightAsOf} onChange={(event) => setRightAsOf(event.target.value)} />
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
              <p className="banner">
                {left.persona.id === right.persona.id
                  ? `${left.persona.name} ở hai ngày hiệu lực: ${formatDay(left.as_of)} và ${formatDay(right.as_of)}.`
                  : `Hai ngày hiệu lực: ${formatDay(left.as_of)} và ${formatDay(right.as_of)}.`}
              </p>
            ) : null}
            {left && right ? (
              <div className="compare">
                <AnswerCard result={left} onOpen={(versionId, nextCitation) => openLibrary(versionId, left.persona.id, nextCitation)} />
                <AnswerCard result={right} onOpen={(versionId, nextCitation) => openLibrary(versionId, right.persona.id, nextCitation)} />
              </div>
            ) : !error ? <div className="empty">Đang lấy câu trả lời...</div> : null}
          </section>
        </main>
      ) : view === "chat" ? (
        <ChatDesk personas={personas} onOpen={openLibrary} />
      ) : view === "tree" ? (
        orgTree ? (
          <OrgTree
            tree={orgTree}
            personas={personas}
            personaId={libraryId}
            canManage={canManage}
            onPersonaChange={(id) => { setFocusId(null); setLibraryId(id); loadDocuments(id, asOf) }}
            onOpen={(versionId) => openLibrary(versionId, libraryId)}
            onDelete={deleteDocument}
          />
        ) : <p className="banner error">Chưa tải được cây tổ chức.</p>
      ) : catalog ? (
        <DocumentDesk
          catalog={catalog}
          documents={documents}
          personas={personas}
          personaId={libraryId}
          asOf={asOf}
          canManage={canManage}
          onPersonaChange={(id) => { setDocuments([]); setLibraryId(id); loadDocuments(id, asOf) }}
          onSaved={() => loadDocuments()}
          focusId={focusId}
          citation={citation}
        />
      ) : <p className="banner error">Chưa tải được danh mục tài liệu.</p>}
    </div>
  )
}
