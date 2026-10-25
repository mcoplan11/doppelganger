import { AllCommunityModule, ModuleRegistry, colorSchemeDark, themeQuartz } from "ag-grid-community";

ModuleRegistry.registerModules([AllCommunityModule]);

// Match the app's Tailwind gray-950 dark palette. Shared by every grid view.
export const gridTheme = themeQuartz.withPart(colorSchemeDark).withParams({
  backgroundColor: "#030712", // gray-950
  headerBackgroundColor: "#111827", // gray-900
  borderColor: "#1f2937", // gray-800
  textColor: "#d1d5db", // gray-300
  headerTextColor: "#9ca3af", // gray-400
  accentColor: "#3b82f6", // blue-500
  fontSize: 12,
});
