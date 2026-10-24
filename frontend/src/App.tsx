import { Navigate, Route, Routes } from "react-router-dom";
import { ConsoleLayout } from "./components/console/shell";
import Landing from "./landing/Landing";
import Operator from "./pages/Operator";
import Officer from "./pages/Officer";
import Sim from "./pages/Sim";
import "./components/console/console.css";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route
        path="/operator"
        element={
          <ConsoleLayout>
            <Operator />
          </ConsoleLayout>
        }
      />
      <Route
        path="/officer"
        element={
          <ConsoleLayout>
            <Officer />
          </ConsoleLayout>
        }
      />
      <Route
        path="/sim"
        element={
          <ConsoleLayout>
            <Sim />
          </ConsoleLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
