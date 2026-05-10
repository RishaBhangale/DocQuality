#!/bin/bash

# Navigate to frontend src
cd /Users/rishabhbhangale/Downloads/semantics/DocQuality/frontend/src

# Create core components directory
mkdir -p core/components

echo "Moving Compliance components..."
cp compliance/components/MetricCard.tsx core/components/
cp compliance/components/ScoreCircle.tsx core/components/
cp compliance/components/HistoryModal.tsx core/components/
cp compliance/components/UploadCard.tsx core/components/

echo "Moving Banking components..."
cp banking/components/IssuesTable.tsx core/components/
cp banking/components/ExecutiveSummary.tsx core/components/
cp banking/components/MetricExplanation.tsx core/components/

echo "Moving Shared visualization components..."
cp compliance/components/MetricRadarChart.tsx core/components/
cp compliance/components/MetricBarChart.tsx core/components/
cp compliance/components/StatusBadge.tsx core/components/
cp compliance/components/AlertBox.tsx core/components/
cp compliance/components/ProgressBar.tsx core/components/
cp compliance/components/SeverityPieChart.tsx core/components/

echo "Done! You can now verify that core/components/ has the shared components."
rm /Users/rishabhbhangale/Downloads/semantics/DocQuality/backend/compliance/services/normalization_service.py
