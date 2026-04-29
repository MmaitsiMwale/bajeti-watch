import { useEffect, useState } from "react";

import { Layout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { CountyPage } from "./pages/CountyPage";
import { HomePage } from "./pages/HomePage";
import { SearchPage } from "./pages/SearchPage";

function currentPath() {
  return window.location.pathname;
}

export function App() {
  const [path, setPath] = useState(currentPath);

  useEffect(() => {
    const handlePopState = () => setPath(currentPath());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(nextPath: string) {
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
  }

  let page = <HomePage onNavigate={navigate} />;
  if (path.startsWith("/county/")) {
    page = <CountyPage county={path.replace("/county/", "")} onNavigate={navigate} />;
  } else if (path === "/search") {
    page = <SearchPage />;
  } else if (path === "/about") {
    page = <AboutPage />;
  }

  return (
    <Layout currentPath={path} onNavigate={navigate}>
      {page}
    </Layout>
  );
}
