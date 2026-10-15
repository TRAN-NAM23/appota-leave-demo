import { useLayoutEffect, useRef, useState } from "react"

const CONTRACTS = {
  full_time: "chính thức",
  intern: "thực tập",
  contractor: "cộng tác",
}

const STATUS_LABELS = {
  published: "Đang ban hành",
  draft: "Dự thảo",
  superseded: "Đã thay thế",
  archived: "Lưu trữ",
}

function OrgNode({ node, onOpen, onDelete, canManage }) {
  const [open, setOpen] = useState(false)
  const [pendingId, setPendingId] = useState(null)
  const [removingId, setRemovingId] = useState(null)
  const [deleteError, setDeleteError] = useState("")
  const count = node.documents.length

  async function removeDocument(document) {
    setRemovingId(document.version_id)
    setDeleteError("")
    try {
      await onDelete(document.version_id)
      setPendingId(null)
    } catch (error) {
      setDeleteError(error.message)
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <li>
      <article className="chart-card" data-kind={node.kind}>
        <div className="chart-head">
          <strong>{node.name}</strong>
          <span className="kind">{node.kind_label}</span>
        </div>
        {node.people.length ? (
          <div className="org-people">
            {node.people.map((person) => (
              <span className="person" key={person.id}>
                {person.name}
                <span> · {CONTRACTS[person.employment_type] || person.employment_type}</span>
              </span>
            ))}
          </div>
        ) : null}
        {count ? (
          <button
            className="doc-toggle"
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((current) => !current)}
          >
            {count} tài liệu
          </button>
        ) : <p className="org-empty">0 tài liệu</p>}
        {open ? (
          <div className="chart-docs">
            {node.documents.map((document) => (
              <div className="chart-doc-row" key={document.version_id}>
                <button className="chart-doc" type="button" onClick={() => onOpen(document.version_id)}>
                  <span className="chart-doc-title">{document.title}</span>
                  <span className="lede">
                    <span className="mono">{document.document_id} v{document.version}</span>
                  </span>
                </button>
                <div className="chart-doc-meta">
                  <span className={`status ${document.status}`}>{STATUS_LABELS[document.status] || document.status}</span>
                {canManage && pendingId === document.version_id ? (
                  <button
                    className="doc-delete"
                    type="button"
                    disabled={removingId === document.version_id}
                    onClick={() => removeDocument(document)}
                  >
                    {removingId === document.version_id ? "..." : "Xóa hẳn"}
                  </button>
                ) : canManage ? (
                  <button className="doc-delete" type="button" onClick={() => setPendingId(document.version_id)}>Xóa</button>
                ) : null}
                </div>
              </div>
            ))}
            {deleteError ? <p className="banner error">{deleteError}</p> : null}
          </div>
        ) : null}
      </article>
      {node.children.length ? (
        <ul>
          {node.children.map((child) => <OrgNode key={child.id} node={child} onOpen={onOpen} onDelete={onDelete} canManage={canManage} />)}
        </ul>
      ) : null}
    </li>
  )
}

function FittedChart({ children }) {
  const frame = useRef(null)
  const content = useRef(null)
  const [fit, setFit] = useState({ scale: 1, height: 0 })

  useLayoutEffect(() => {
    const frameEl = frame.current
    const contentEl = content.current
    if (!frameEl || !contentEl) return

    const measure = () => {
      const tree = contentEl.querySelector("ul")
      const available = frameEl.clientWidth
      const width = tree ? tree.offsetWidth : 0
      const height = tree ? tree.offsetHeight : 0
      if (!available || !width || !height) return
      const scale = Math.min(1, available / width)
      const nextHeight = Math.ceil(height * scale)
      setFit((current) => (
        Math.abs(current.scale - scale) < 0.01 && current.height === nextHeight
          ? current
          : { scale, height: nextHeight }
      ))
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(frameEl)
    observer.observe(contentEl)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="chart" ref={frame}>
      <div className="chart-fit" style={{ height: fit.height || undefined }}>
        <div className="chart-scale" ref={content} style={{ transform: `scale(${fit.scale})` }}>
          {children}
        </div>
      </div>
    </div>
  )
}

export default function OrgTree({ tree, onOpen, onDelete, canManage, personas, personaId, onPersonaChange }) {
  return (
    <div className="org-page">
      <div className="library-head">
        <h2>Cây tổ chức</h2>
        <label>Người đang xem
          <select value={personaId} onChange={(event) => onPersonaChange(event.target.value)}>
            {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name} · {persona.org} · {persona.clearance === "restricted" ? "hạn chế" : persona.clearance === "confidential" ? "mật" : "nội bộ"}</option>)}
          </select>
        </label>
      </div>
      <div className="level-row">
        {tree.levels.map((level) => (
          <article className="level-card" key={level.kind} data-kind={level.kind}>
            <p className="kicker">{level.label}</p>
            <strong>{level.documents}</strong>
            <p className="lede">tài liệu · {level.units} đơn vị</p>
          </article>
        ))}
      </div>
      <section className="tree">
        <FittedChart>
          <ul>
            {tree.tree.map((node) => <OrgNode key={node.id} node={node} onOpen={onOpen} onDelete={onDelete} canManage={canManage} />)}
          </ul>
        </FittedChart>
      </section>
    </div>
  )
}
