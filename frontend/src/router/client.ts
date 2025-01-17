import { API } from "@/api";
import { router } from "@/router";
import { notice } from "@/utils/notification";
import { appStore as store } from "@/store/global";

export async function checkTokenValidity(): Promise<boolean> {
  const api = new API();
  const token = localStorage.getItem("jwtToken");
  if (token) {
    try {
      await api.isAvailable();
    } catch (error) {
      localStorage.clear();
      return false;
    }
    store().isAuth = true;
    return true;
  }
  return false;
}

export function routerTo(to: string): void {
  if (!store().choiceProject.project_id) {
    notice.warning("请先选择一项实例");
    return;
  }
  store().nowPath = to;
  router.push(to);
}
