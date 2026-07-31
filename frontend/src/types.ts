export type Role='employee'|'admin'|'super_admin';
export interface Profile{id:number;telegram_id:number;username?:string;full_name:string;photo_url?:string;role:Role;role_label:string;pvz?:{id:number;name:string};created_at:string;xp:number;level:number;level_progress:number;xp_to_next:number;streak:number;stats:{tests:number;average:number;best:number;correct:number;errors:number}}
export interface Question{id:number;text:string;category:string;type:string;options:{id:number;text:string}[]}
export interface Attempt{attempt_id:string;status:string;position:number;total:number;question:Question}
declare global{interface Window{Telegram?:{WebApp:{initData:string;ready():void;expand():void;close():void;enableClosingConfirmation():void;disableClosingConfirmation():void;setHeaderColor(color:string):void;setBackgroundColor(color:string):void;HapticFeedback?:{impactOccurred(style:string):void;notificationOccurred(type:string):void}}}}}
