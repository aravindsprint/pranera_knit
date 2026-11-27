// Excel / PDF export for the table-view pages.
//
// Column definition (shared with components/DataTable.vue):
//   { key, label, type: 'text' | 'num' | 'int' | 'pct' | 'date' | 'datetime',
//     width?, pdf?: false (leave out of the PDF), value?: row => any }
//
// exceljs / jspdf are imported lazily, so they are only downloaded the first
// time someone actually exports — they never weigh down the normal app bundle.

export function cellValue(col, row) {
  return col.value ? col.value(row) : row[col.key]
}

export function parseDT(v) {
  if (!v) return null
  if (v instanceof Date) return isNaN(v) ? null : v
  const d = new Date(String(v).replace(' ', 'T'))
  return isNaN(d) ? null : d
}

export function formatCell(col, v) {
  if (v === null || v === undefined || v === '') return ''
  switch (col.type) {
    case 'num':
      return (Number(v) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    case 'int':
      return (Number(v) || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })
    case 'pct':
      return `${(Number(v) || 0).toFixed(1)}%`
    case 'date': {
      const d = parseDT(v)
      return d ? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : ''
    }
    case 'datetime': {
      const d = parseDT(v)
      return d ? d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) : ''
    }
    default:
      return String(v)
  }
}

const isNumeric = t => t === 'num' || t === 'int' || t === 'pct'

export function stamp() {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

// Excel date cells: exceljs writes JS Dates as UTC, so shift local wall-clock
// time into UTC to make the sheet show the same time as the app (IST).
function excelDate(v) {
  const d = parseDT(v)
  return d ? new Date(d.getTime() - d.getTimezoneOffset() * 60000) : null
}

/**
 * sheets: [{ name, title?, subtitle?, columns, rows }]
 */
export async function exportExcel(filename, sheets) {
  const { default: ExcelJS } = await import('exceljs')
  const wb = new ExcelJS.Workbook()
  wb.creator = 'Pranera Knit App'
  wb.created = new Date()

  for (const s of sheets) {
    const ws = wb.addWorksheet(s.name.slice(0, 31))
    let r = 1
    if (s.title) {
      ws.getCell(r, 1).value = s.title
      ws.getCell(r, 1).font = { bold: true, size: 14 }
      r++
    }
    if (s.subtitle) {
      ws.getCell(r, 1).value = s.subtitle
      ws.getCell(r, 1).font = { italic: true, size: 10, color: { argb: 'FF64748B' } }
      r++
    }
    if (s.title || s.subtitle) r++

    const headerRow = r
    s.columns.forEach((c, i) => {
      const cell = ws.getCell(headerRow, i + 1)
      cell.value = c.label
      cell.font = { bold: true, color: { argb: 'FFFFFFFF' } }
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF0F6E56' } }
      cell.alignment = { vertical: 'middle', horizontal: isNumeric(c.type) ? 'right' : 'left', wrapText: true }
      cell.border = { bottom: { style: 'thin', color: { argb: 'FF94A3B8' } } }
    })
    ws.getRow(headerRow).height = 30

    s.rows.forEach((row, ri) => {
      const excelRow = ws.getRow(headerRow + 1 + ri)
      s.columns.forEach((c, ci) => {
        const cell = excelRow.getCell(ci + 1)
        let v = cellValue(c, row)
        if (v === undefined || v === '') v = null
        if (v !== null) {
          if (isNumeric(c.type)) {
            v = Number(v) || 0
            if (c.type === 'pct') v = v / 100
          } else if (c.type === 'date' || c.type === 'datetime') {
            v = excelDate(v)
          }
        }
        cell.value = v
        if (c.type === 'num') cell.numFmt = '#,##0.00'
        if (c.type === 'int') cell.numFmt = '#,##0'
        if (c.type === 'pct') cell.numFmt = '0.0%'
        if (c.type === 'date') cell.numFmt = 'dd-mmm-yyyy'
        if (c.type === 'datetime') cell.numFmt = 'dd-mmm-yyyy hh:mm'
      })
      if (ri % 2 === 1) {
        excelRow.eachCell({ includeEmpty: true }, cell => {
          cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF1F5F9' } }
        })
      }
    })

    s.columns.forEach((c, i) => {
      ws.getColumn(i + 1).width = c.width || (isNumeric(c.type) ? 13 : c.type === 'datetime' ? 18 : c.type === 'date' ? 13 : 16)
    })
    ws.views = [{ state: 'frozen', ySplit: headerRow }]
    if (s.rows.length) {
      ws.autoFilter = { from: { row: headerRow, column: 1 }, to: { row: headerRow + s.rows.length, column: s.columns.length } }
    }
  }

  const buf = await wb.xlsx.writeBuffer()
  download(new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), filename)
}

/**
 * opts: { title, subtitle?, columns, rows, rowStyle?: row => { fillColor, textColor } }
 * Columns with `pdf: false` are skipped so the landscape page stays readable.
 */
export async function exportPdf(filename, { title, subtitle, columns, rows, rowStyle }) {
  const [{ jsPDF }, { autoTable }] = await Promise.all([import('jspdf'), import('jspdf-autotable')])
  const cols = columns.filter(c => c.pdf !== false)
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' })
  const pageW = doc.internal.pageSize.getWidth()
  const pageH = doc.internal.pageSize.getHeight()

  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.text(title, 30, 34)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(100)
  doc.text(subtitle || '', 30, 50)
  doc.setTextColor(0)

  const columnStyles = {}
  cols.forEach((c, i) => { if (isNumeric(c.type)) columnStyles[i] = { halign: 'right' } })

  autoTable(doc, {
    startY: 62,
    head: [cols.map(c => c.label)],
    body: rows.map(r => cols.map(c => formatCell(c, cellValue(c, r)))),
    styles: { fontSize: cols.length > 14 ? 6.5 : 7.5, cellPadding: 3, overflow: 'linebreak', valign: 'middle' },
    headStyles: { fillColor: [15, 110, 86], textColor: 255, fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [241, 245, 249] },
    columnStyles,
    margin: { left: 30, right: 30, top: 30, bottom: 30 },
    didParseCell: data => {
      if (rowStyle && data.section === 'body') {
        const st = rowStyle(rows[data.row.index])
        if (st) Object.assign(data.cell.styles, st)
      }
    },
    didDrawPage: () => {
      const n = doc.internal.getNumberOfPages()
      doc.setFontSize(8)
      doc.setTextColor(140)
      doc.text(`Page ${n}`, pageW - 30, pageH - 14, { align: 'right' })
      doc.text(`Pranera Knit App · generated ${new Date().toLocaleString('en-IN')}`, 30, pageH - 14)
      doc.setTextColor(0)
    },
  })

  doc.save(filename)
}
