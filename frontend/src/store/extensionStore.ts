import { defineStore } from "pinia";
import { API } from "@/api";
import { ToastWrapper } from "@/utils/notification";
import { Adapter, Driver, Plugin } from "@/api/models";
import { AxiosError } from "axios";

const api = new API();
const notice = new ToastWrapper("Nonebot Store");

export const nonebotExtensionStore = defineStore("nonebotExtensionStore", {
  state() {
    return {
      searchInput: "",
      requesting: false,
      storeData: [] as Plugin[] | Adapter[] | Driver[],
      nowPage: 0,
      totalPage: 0,
      totalItem: 0,
      choiceClass: "plugin",
      choiceItem: Object() as Plugin | Adapter | Driver,
      sideNavShow: true,
    };
  },
  actions: {
    assignClass(cls: string) {
      this.choiceClass = cls;
    },

    turnPage(page: number) {
      if (page >= 0) {
        this.nowPage = page;
      } else {
        this.nowPage = 0;
      }

      if (page >= this.totalPage) {
        this.nowPage = this.totalPage;
      }
    },

    async updateData(projectID: string) {
      const isSearch = this.searchInput ? true : false;
      this.requesting = true;
      if (this.choiceClass === "plugin") {
        await api
          .getPlugins(this.nowPage, isSearch, projectID)
          .then((resp) => {
            this.requesting = false;
            this.totalPage = resp.total_page;
            this.totalItem = resp.total_item;
            this.storeData = resp.data;
          })
          .catch((error: AxiosError) => {
            this.requesting = false;
            let reason: string;
            if (error.response) {
              reason = (error.response.data as { detail: string })?.detail;
            } else {
              reason = error.message;
            }
            notice.error(`获取插件列表失败：${reason}`);
          });
      }

      if (this.choiceClass === "adapter") {
        await api
          .getAdapters(this.nowPage, isSearch, projectID)
          .then((resp) => {
            this.requesting = false;
            this.storeData = resp.data;
            this.totalPage = resp.total_page;
            this.totalItem = resp.total_item;
          })
          .catch((error: AxiosError) => {
            this.requesting = false;
            let reason: string;
            if (error.response) {
              reason = (error.response.data as { detail: string })?.detail;
            } else {
              reason = error.message;
            }
            notice.error(`获取适配器列表失败：${reason}`);
          });
      }

      if (this.choiceClass === "driver") {
        await api
          .getDrivers(this.nowPage, isSearch, projectID)
          .then((resp) => {
            this.requesting = false;
            this.storeData = resp.data;
            this.totalPage = resp.total_page;
            this.totalItem = resp.total_item;
          })
          .catch((error: AxiosError) => {
            this.requesting = false;
            let reason: string;
            if (error.response) {
              reason = (error.response.data as { detail: string })?.detail;
            } else {
              reason = error.message;
            }
            notice.error(`获取驱动器列表失败：${reason}`);
          });
      }
    },

    async updateDataBySearch(projectID: string) {
      this.requesting = true;
      await api
        .searchStore(projectID, this.choiceClass, this.searchInput)
        .then((resp) => {
          this.requesting = false;
          this.storeData = resp.data;
          this.totalPage = resp.total_page;
          this.totalItem = resp.total_item;
        })
        .catch((error: AxiosError) => {
          this.requesting = false;
          let reason: string;
          if (error.response) {
            reason = (error.response.data as { detail: string })?.detail;
          } else {
            reason = error.message;
          }
          notice.error(`搜索 NoneBot 拓展商店失败：${reason}`);
        });
    },

    async refresh() {
      this.requesting = true;
      await api
        .refreshStore()
        .then(() => {
          this.requesting = false;
        })
        .catch((error: AxiosError) => {
          this.requesting = false;
          let reason: string;
          if (error.response) {
            reason = (error.response.data as { detail: string })?.detail;
          } else {
            reason = error.message;
          }
          notice.error(`NoneBot 拓展商店刷新失败：${reason}`);
        });
    },

    switchNavVisible() {
      this.sideNavShow = !this.sideNavShow;
    },
  },
});
