export async function request(url, options) {
  const response = await fetch(url, options)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload.detail
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item.msg).join(" ")
        : "Không gọi được dịch vụ."
    throw new Error(message)
  }
  return payload
}

export function remove(url) {
  return request(url, { method: "DELETE" })
}

export function post(url, body) {
  return request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
