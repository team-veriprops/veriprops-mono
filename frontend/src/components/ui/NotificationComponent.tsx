import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@components/3rdparty/ui/dropdown-menu";
import { Separator } from "@components/3rdparty/ui/separator";
import ToolTipComponent from "./ToolTipComponent";
import { Bell, Dot, Settings, Trash2 } from "lucide-react";
import { Button } from "@components/3rdparty/ui/button";
import { Badge } from "@components/3rdparty/ui/badge";
import { redirect } from "next/navigation";
interface Notification {
  id: string;
  title: string;
  type: string;
  time: string;
}

interface NotificationComponentProps {
  notifications: Notification[];
}

export default function NotificationComponent({
  notifications,
}: NotificationComponentProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {notifications.length > 0 && (
            <Badge className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs">
              {notifications.length}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="p-4">
          <div className="flex justify-between">
            <h4 className="font-medium mb-2">Notifications</h4>
            <Settings
              onClick={() => redirect("/portal/settings/notifications")}
              className="text-muted-foreground hover:text-black cursor-pointer"
              size={17}
            />
          </div>
          <Separator className="mb-6" />

          <div className="space-y-2">
            {notifications.length > 0 ? (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  className="flex justify-between group p-2 cursor-pointer hover:bg-gray-50"
                >
                  <div>
                    <p className="text-sm">{notification.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {notification.time}
                    </p>
                  </div>
                  <div>
                    <Dot size={40} className="inline text-accent-strong" />
                    <ToolTipComponent label={"Delete"}>
                      <Trash2
                        size={16}
                        className="hidden group-hover:inline cursor-pointer text-red-500"
                      />
                    </ToolTipComponent>
                  </div>
                </div>
              ))
            ) : (
              <div>
                <p className="text-sm">No new notifications</p>
              </div>
            )}
          </div>
        </div>
        <Separator className="mb-2" />
        <div className="text-center cursor-pointer p-1 text-muted-foreground hover:text-black">
          Archive all
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
