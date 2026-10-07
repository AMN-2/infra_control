import { createApp } from "vue";
import { createPinia } from "pinia";
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/jetbrains-mono";
import App from "./App.vue";
import { router } from "./router";
import { installMotionEnvironment } from "./design/motion";
import "./main.css";

installMotionEnvironment();
createApp(App).use(createPinia()).use(router).mount("#app");
