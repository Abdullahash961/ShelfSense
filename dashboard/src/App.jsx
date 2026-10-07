import { useState, useCallback } from 'react';
import { useStatus, useAlerts, useToast } from './hooks/useApi';

import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import ZoneGrid from './components/ZoneGrid';
import AlertsPanel from './components/AlertsPanel';
import TrendChart from './components/TrendChart';
import AnalyzePanel from './components/AnalyzePanel';
import ZoneManager from './components/ZoneManager';
import ImageModal from './components/ImageModal';
import CameraPanel from './components/CameraPanel';

function App() {
  const { data: statusData, loading: statusLoading, refresh: refreshStatus } = useStatus();
  const { data: alertsData, loading: alertsLoading, refresh: refreshAlerts } = useAlerts();
  const { toast, showToast } = useToast();

  const [viewImage, setViewImage] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = useCallback(() => {
    refreshStatus();
    refreshAlerts();
    setRefreshKey((k) => k + 1);
  }, [refreshStatus, refreshAlerts]);

  return (
    <div className="app-container">
      <Header 
        lastAnalyzed={statusData?.analyzed_at} 
        onRefresh={handleRefresh} 
        loading={statusLoading || alertsLoading} 
      />

      <SummaryCards 
        summary={statusData?.summary} 
        totalZones={statusData?.zones?.length}
        zones={statusData?.zones}
      />

      <div className="grid-2">
        <div>
          <CameraPanel onAnalysisComplete={handleRefresh} showToast={showToast} />
          <ZoneGrid 
            zones={statusData?.zones} 
            onViewImage={(path) => setViewImage(path)} 
          />
          <AnalyzePanel onSuccess={handleRefresh} showToast={showToast} />
        </div>
        <div>
          <AlertsPanel alerts={alertsData} loading={alertsLoading} />
          <TrendChart zones={statusData?.zones} />
        </div>
      </div>

      <ZoneManager showToast={showToast} refreshKey={refreshKey} />

      {viewImage && (
        <ImageModal 
          zone={viewImage} 
          onClose={() => setViewImage(null)} 
        />
      )}

      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}

export default App;

