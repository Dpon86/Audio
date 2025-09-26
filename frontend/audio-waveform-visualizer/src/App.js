import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Layout from "./components/layouts/Layout";
import FrontPage from "./screens/frontpage";
import AudioPage from "./screens/AudioPage";
import EditPage from "./screens/EditPage";
import PDFAnalysisPage from "./screens/PDFAnalysisPage";

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<FrontPage />} />
          <Route path="/AudioUpload" element={<AudioPage />} />
          <Route path="/EditPage" element={<EditPage />} />
          <Route path="/PDFAnalysis" element={<PDFAnalysisPage />} />

        </Routes>
      </Layout>
    </Router>
  );
}

export default App;