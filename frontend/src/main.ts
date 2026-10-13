import { ElAside, ElContainer, ElMain } from "element-plus/es/components/container/index";
import { ElButton } from "element-plus/es/components/button/index";
import { ElCheckbox } from "element-plus/es/components/checkbox/index";
import { ElDialog } from "element-plus/es/components/dialog/index";
import { ElForm, ElFormItem } from "element-plus/es/components/form/index";
import { ElIcon } from "element-plus/es/components/icon/index";
import { ElInput } from "element-plus/es/components/input/index";
import { ElInputNumber } from "element-plus/es/components/input-number/index";
import { ElMenu, ElMenuItem } from "element-plus/es/components/menu/index";
import { ElOption, ElSelect } from "element-plus/es/components/select/index";
import { ElPagination } from "element-plus/es/components/pagination/index";
import { ElSegmented } from "element-plus/es/components/segmented/index";
import { ElSwitch } from "element-plus/es/components/switch/index";
import { ElTable, ElTableColumn } from "element-plus/es/components/table/index";
import { ElTabPane, ElTabs } from "element-plus/es/components/tabs/index";
import { ElTooltip } from "element-plus/es/components/tooltip/index";
import "element-plus/dist/index.css";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./assets/styles.css";
import "./assets/configuration.css";

const app = createApp(App).use(createPinia()).use(router);

[
  ElAside,
  ElButton,
  ElCheckbox,
  ElContainer,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElPagination,
  ElSegmented,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTooltip
].forEach((component) => app.component(component.name!, component));

app.mount("#app");
