import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { MapPage } from "@/features/map/MapPage";
import { AirQualityPage } from "@/features/air-quality/AirQualityPage";
import { LandCoverPage } from "@/features/land-cover/LandCoverPage";
import { LandUseScenariosPage } from "@/features/scenarios/LandUseScenariosPage";
import { LocalQuestionsPage } from "@/features/local/LocalQuestionsPage";
import { RelationshipsPage } from "@/features/relationships/RelationshipsPage";
import { PriorityPage } from "@/features/priority/PriorityPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { DatasetsPage } from "@/features/datasets/DatasetsPage";
import { MethodologyPage } from "@/features/methodology/MethodologyPage";
import { PresentationPage } from "@/features/presentation/PresentationPage";
import { ProjectionPage } from "@/features/projection/ProjectionPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="air-quality" element={<AirQualityPage />} />
        <Route path="land-cover" element={<LandCoverPage />} />
        <Route path="scenarios" element={<LandUseScenariosPage />} />
        <Route path="local-questions" element={<LocalQuestionsPage />} />
        <Route path="relationships" element={<RelationshipsPage />} />
        <Route path="projection" element={<ProjectionPage />} />
        <Route path="priority" element={<PriorityPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="datasets" element={<DatasetsPage />} />
        <Route path="methodology" element={<MethodologyPage />} />
        <Route path="presentation" element={<PresentationPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
