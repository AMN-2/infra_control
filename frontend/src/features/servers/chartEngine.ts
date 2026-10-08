import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

/** Kept behind a dynamic import so ECharts never enters the initial application bundle. */
export function initMetricChart(element: HTMLElement): ECharts {
	return init(element);
}
