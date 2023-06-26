import { defineStore } from "pinia";
import { NoticeDetail } from "@/core/notification";

export const globalStore = defineStore("globalStore", {
  state: () => {
    return {
      nowPageName: "",
      showMenu: true,
      isAuth: false,
      choiceProjectID: "",
    };
  },
});

export const notifications = defineStore("notifications", {
  state: (): { notices: NoticeDetail[] } => {
    return {
      notices: [],
    };
  },
});
