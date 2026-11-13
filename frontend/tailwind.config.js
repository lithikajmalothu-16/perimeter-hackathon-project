/** Artifact palette: cream, burnt orange, ink, sticky yellow. Hard offset shadows, no blur. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#1C2426", cream: "#F4F0EA", page: "#EAE5DE", orange: "#C8642A", rust: "#8A3E12", sticky: "#F7F3B5",
                chip: "#E3DCCF", muted: "#4A4F50", dash: "#8C8478", danger: "#A12A2A" },
      fontFamily: { display: ["Archivo", "sans-serif"], body: ["'Work Sans'", "system-ui", "sans-serif"] },
      boxShadow: { hard: "6px 6px 0 #1C2426", hardlg: "8px 8px 0 #1C2426", hardsm: "4px 4px 0 #1C2426", rust: "6px 6px 0 #8A3E12" },
      borderWidth: { 2.5: "2.5px" },
    },
  },
  plugins: [],
};
