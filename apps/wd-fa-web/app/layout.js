import "./globals.css";

export const metadata = {
  title: "WD Semantic Failure Analysis",
  description: "Evidence-bound HDD failure-analysis workbench",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
