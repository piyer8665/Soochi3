const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, Header, Footer, ImageRun, PageBreak,
  TableOfContents
} = require('docx');
const fs = require('fs');

const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const outputPath = process.argv[3];

const BLUE = "1F4E79";
const LIGHT_BLUE = "D5E8F0";
const LIGHT_GRAY = "F5F5F5";
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 3120, type: WidthType.DXA },
    shading: opts.shading ? { fill: opts.shading, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({
        text: String(text || ''),
        bold: opts.bold || false,
        size: opts.size || 18,
        color: opts.color || "000000",
        font: "Arial"
      })]
    })]
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 32, color: BLUE, font: "Arial" })],
    spacing: { before: 360, after: 180 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 1 } }
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 24, color: BLUE, font: "Arial" })],
    spacing: { before: 240, after: 120 }
  });
}

function para(text, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
    spacing: { before: opts.before || 0, after: opts.after || 80 },
    children: [new TextRun({
      text: String(text || ''),
      bold: opts.bold || false,
      size: opts.size || 20,
      color: opts.color || "000000",
      font: "Arial"
    })]
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 120, after: 120 } });
}

const children = [];

// Title Page
children.push(spacer(), spacer(), spacer());
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 240 },
  children: [new TextRun({ text: "Soochi Data Report", bold: true, size: 56, color: BLUE, font: "Arial" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 160 },
  children: [new TextRun({ text: data.dataset_name, bold: true, size: 36, color: "444444", font: "Arial" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 80 },
  children: [new TextRun({ text: `${data.total_rows.toLocaleString()} rows  ·  ${data.total_columns} variables`, size: 24, color: "666666", font: "Arial" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: `Generated: ${data.generated_at}`, size: 20, color: "888888", font: "Arial" })]
}));
children.push(new Paragraph({ children: [new PageBreak()], spacing: { before: 480 } }));

// Table of Contents placeholder
children.push(heading1("Table of Contents"));
children.push(new TableOfContents("Table of Contents", {
  hyperlink: true,
  headingStyleRange: "1-2",
  stylesWithLevels: [
    { styleName: "Heading 1", level: 1 },
    { styleName: "Heading 2", level: 2 },
  ],
}));
children.push(new Paragraph({ children: [new PageBreak()] }));

// Variable Summary
children.push(heading1("Variable Summary"));
children.push(spacer());

const summaryRows = [
  new TableRow({
    tableHeader: true,
    children: [
      cell("Variable", { width: 2800, bold: true, shading: BLUE, color: "FFFFFF" }),
      cell("Type", { width: 2200, bold: true, shading: BLUE, color: "FFFFFF" }),
      cell("Coded", { width: 900, bold: true, shading: BLUE, color: "FFFFFF" }),
      cell("Sample Codes", { width: 3460, bold: true, shading: BLUE, color: "FFFFFF" }),
    ]
  })
];

data.entries.forEach((entry, i) => {
  const codes = entry.coding_table && entry.coding_table.length > 0
    ? entry.coding_table.slice(0, 6).map(r => `${r.code}=${r.name}`).join(', ') +
      (entry.coding_table.length > 6 ? ` (+${entry.coding_table.length - 6} more)` : '')
    : '—';
  summaryRows.push(new TableRow({
    children: [
      cell(entry.column, { width: 2800, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
      cell(entry.variable_type, { width: 2200, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
      cell(entry.coding_table && entry.coding_table.length > 0 ? 'Yes' : 'No', { width: 900, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
      cell(codes, { width: 3460, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
    ]
  }));
});

children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2800, 2200, 900, 3460],
  rows: summaryRows
}));
children.push(new Paragraph({ children: [new PageBreak()] }));

// Data Dictionary
children.push(heading1("Data Dictionary"));

data.entries.forEach(entry => {
  children.push(spacer());
  children.push(heading2(entry.column));
  children.push(para(`Type: ${entry.variable_type}`, { bold: true }));
  if (entry.description) children.push(para(entry.description));
  if (entry.range) children.push(para(`Range: ${entry.range}`, { color: "555555" }));
  if (entry.mean !== null && entry.mean !== undefined && entry.variable_type === 'Continuous') {
    children.push(para(`Mean: ${entry.mean}  |  Median: ${entry.median}  |  SD: ${entry.std}`, { color: "555555" }));
  }

  if (entry.coding_table && entry.coding_table.length > 0) {
    children.push(para("Coding Table:", { bold: true, before: 120 }));
    const codeRows = [
      new TableRow({
        tableHeader: true,
        children: [
          cell("Code", { width: 1200, bold: true, shading: LIGHT_BLUE }),
          cell("Name", { width: 3000, bold: true, shading: LIGHT_BLUE }),
          cell("Definition", { width: 5160, bold: true, shading: LIGHT_BLUE }),
        ]
      })
    ];
    entry.coding_table.forEach((row, i) => {
      codeRows.push(new TableRow({
        children: [
          cell(row.code, { width: 1200, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
          cell(row.name, { width: 3000, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
          cell(row.definition || '', { width: 5160, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
        ]
      }));
    });
    children.push(new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [1200, 3000, 5160],
      rows: codeRows
    }));
  }

  if (entry.data_quality_notes && entry.data_quality_notes.length > 0) {
    children.push(para("Data Quality Notes:", { bold: true, before: 120 }));
    entry.data_quality_notes.forEach(note => {
      children.push(para(`• ${note}`, { color: "B8440A" }));
    });
  }

  children.push(new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "DDDDDD", space: 1 } },
    spacing: { before: 160, after: 0 }
  }));
});

children.push(new Paragraph({ children: [new PageBreak()] }));

// Normality Testing
if (data.normality && data.normality.results && data.normality.results.length > 0) {
  children.push(heading1("Normality Testing"));
  children.push(para(data.normality.overall_recommendation, { color: "333333", before: 120, after: 200 }));

  const normRows = [
    new TableRow({
      tableHeader: true,
      children: [
        cell("Variable", { width: 2000, bold: true, shading: BLUE, color: "FFFFFF" }),
        cell("Test", { width: 1800, bold: true, shading: BLUE, color: "FFFFFF" }),
        cell("p-value", { width: 1200, bold: true, shading: BLUE, color: "FFFFFF" }),
        cell("Passes", { width: 900, bold: true, shading: BLUE, color: "FFFFFF" }),
        cell("Skewness", { width: 1200, bold: true, shading: BLUE, color: "FFFFFF" }),
        cell("Recommendation", { width: 2260, bold: true, shading: BLUE, color: "FFFFFF" }),
      ]
    })
  ];

  data.normality.results.forEach((result, i) => {
    normRows.push(new TableRow({
      children: [
        cell(result.column, { width: 2000, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
        cell(result.test, { width: 1800, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
        cell(result.p_value.toFixed(4), { width: 1200, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
        cell(result.passes ? 'Yes' : 'No', { width: 900, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF", color: result.passes ? "1F7A1F" : "B80000" }),
        cell(result.skewness !== undefined ? result.skewness.toFixed(4) : '—', { width: 1200, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
        cell(result.recommendation, { width: 2260, shading: i % 2 === 0 ? LIGHT_GRAY : "FFFFFF" }),
      ]
    }));
  });

  children.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2000, 1800, 1200, 900, 1200, 2260],
    rows: normRows
  }));

  data.normality.results.forEach((result, idx) => {
    // Each variable starts on a new page to keep heading+stats+images together
    if (idx > 0) children.push(new Paragraph({ children: [new PageBreak()] }));
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_2,
      keepNext: true,
      children: [new TextRun({ text: result.column, bold: true, size: 24, color: BLUE, font: "Arial" })],
      spacing: { before: 240, after: 80 }
    }));
    children.push(new Paragraph({
      keepNext: true,
      spacing: { before: 0, after: 80 },
      children: [new TextRun({ text: `Mean: ${result.mean?.toFixed(4)}  |  SD: ${result.std?.toFixed(4)}  |  Skewness: ${result.skewness?.toFixed(4)}  |  Kurtosis: ${result.kurtosis?.toFixed(4)}`, color: "555555", size: 20, font: "Arial" })]
    }));
    children.push(new Paragraph({
      keepNext: true,
      spacing: { before: 0, after: 120 },
      children: [new TextRun({ text: result.interpretation, color: result.passes ? "1F7A1F" : "B80000", size: 20, font: "Arial" })]
    }));
    if (result.histogram) {
      try {
        children.push(new Paragraph({
          keepNext: true,
          spacing: { before: 0, after: 120 },
          children: [new ImageRun({ data: Buffer.from(result.histogram, 'base64'), transformation: { width: 600, height: 420 }, type: 'png' })]
        }));
      } catch(e) {}
    }
    if (result.qq_plot) {
      try {
        children.push(new Paragraph({
          spacing: { before: 0, after: 120 },
          children: [new ImageRun({ data: Buffer.from(result.qq_plot, 'base64'), transformation: { width: 600, height: 420 }, type: 'png' })]
        }));
      } catch(e) {}
    }
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: {
      first: new Header({
        children: [new Paragraph({ children: [] })]
      }),
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: `Soochi Data Report  |  ${data.dataset_name}`, size: 16, color: "888888", font: "Arial" })] })] })
    },
    footers: {
      first: new Footer({
        children: [new Paragraph({ children: [] })]
      }),
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Generated by Soochi  |  Page ", size: 16, color: "888888", font: "Arial" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "888888", font: "Arial" }), new TextRun({ text: " of ", size: 16, color: "888888", font: "Arial" }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "888888", font: "Arial" })] })] })
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log('done');
}).catch(err => {
  console.error('ERROR:', err.message);
  process.exit(1);
});
