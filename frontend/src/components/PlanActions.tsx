import { ReactElement, cloneElement } from "react";

type PlanActionsProps = {
  plan: string;
  trigger: ReactElement;
};

function PlanActions({ plan, trigger }: PlanActionsProps) {
  const handleExport = () => {
    const blob = new Blob([plan], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `处置方案_${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "")}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return cloneElement(trigger, { onClick: handleExport });
}

export default PlanActions;
