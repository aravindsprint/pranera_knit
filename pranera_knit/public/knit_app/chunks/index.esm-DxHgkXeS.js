import{r as y,h as m,C as T,e as M,E as X,q as P,F as ve,t as I,l as Se,v as Ae,u as Ee,w as _e,x as A}from"./index.esm2017-BJtptJo2.js";const Q="@firebase/installations",R="0.6.9";/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Z=1e4,ee=`w:${R}`,te="FIS_v2",Oe="https://firebaseinstallations.googleapis.com/v1",Ce=60*60*1e3,Ne="installations",De="Installations";/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Me={"missing-app-config-values":'Missing App configuration value: "{$valueName}"',"not-registered":"Firebase Installation is not registered.","installation-not-found":"Firebase Installation not found.","request-failed":'{$requestName} request failed with error "{$serverCode} {$serverStatus}: {$serverMessage}"',"app-offline":"Could not process request. Application offline.","delete-pending-registration":"Can't delete installation while there is a pending registration request."},g=new X(Ne,De,Me);function ne(e){return e instanceof ve&&e.code.includes("request-failed")}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function oe({projectId:e}){return`${Oe}/projects/${e}/installations`}function ie(e){return{token:e.token,requestStatus:2,expiresIn:Re(e.expiresIn),creationTime:Date.now()}}async function re(e,t){const o=(await t.json()).error;return g.create("request-failed",{requestName:e,serverCode:o.code,serverMessage:o.message,serverStatus:o.status})}function ae({apiKey:e}){return new Headers({"Content-Type":"application/json",Accept:"application/json","x-goog-api-key":e})}function Pe(e,{refreshToken:t}){const n=ae(e);return n.append("Authorization",je(t)),n}async function se(e){const t=await e();return t.status>=500&&t.status<600?e():t}function Re(e){return Number(e.replace("s","000"))}function je(e){return`${te} ${e}`}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Fe({appConfig:e,heartbeatServiceProvider:t},{fid:n}){const o=oe(e),i=ae(e),r=t.getImmediate({optional:!0});if(r){const d=await r.getHeartbeatsHeader();d&&i.append("x-firebase-client",d)}const a={fid:n,authVersion:te,appId:e.appId,sdkVersion:ee},c={method:"POST",headers:i,body:JSON.stringify(a)},f=await se(()=>fetch(o,c));if(f.ok){const d=await f.json();return{fid:d.fid||n,registrationStatus:2,refreshToken:d.refreshToken,authToken:ie(d.authToken)}}else throw await re("Create Installation",f)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function ce(e){return new Promise(t=>{setTimeout(t,e)})}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Ke(e){return btoa(String.fromCharCode(...e)).replace(/\+/g,"-").replace(/\//g,"_")}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const $e=/^[cdef][\w-]{21}$/,D="";function qe(){try{const e=new Uint8Array(17);(self.crypto||self.msCrypto).getRandomValues(e),e[0]=112+e[0]%16;const n=xe(e);return $e.test(n)?n:D}catch{return D}}function xe(e){return Ke(e).substr(0,22)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function v(e){return`${e.appName}!${e.appId}`}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const ue=new Map;function de(e,t){const n=v(e);fe(n,t),Le(n,t)}function fe(e,t){const n=ue.get(e);if(n)for(const o of n)o(t)}function Le(e,t){const n=Ve();n&&n.postMessage({key:e,fid:t}),Be()}let l=null;function Ve(){return!l&&"BroadcastChannel"in self&&(l=new BroadcastChannel("[Firebase] FID Change"),l.onmessage=e=>{fe(e.data.key,e.data.fid)}),l}function Be(){ue.size===0&&l&&(l.close(),l=null)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const He="firebase-installations-database",We=1,w="firebase-installations-store";let E=null;function j(){return E||(E=P(He,We,{upgrade:(e,t)=>{switch(t){case 0:e.createObjectStore(w)}}})),E}async function k(e,t){const n=v(e),i=(await j()).transaction(w,"readwrite"),r=i.objectStore(w),a=await r.get(n);return await r.put(t,n),await i.done,(!a||a.fid!==t.fid)&&de(e,t.fid),t}async function pe(e){const t=v(e),o=(await j()).transaction(w,"readwrite");await o.objectStore(w).delete(t),await o.done}async function S(e,t){const n=v(e),i=(await j()).transaction(w,"readwrite"),r=i.objectStore(w),a=await r.get(n),c=t(a);return c===void 0?await r.delete(n):await r.put(c,n),await i.done,c&&(!a||a.fid!==c.fid)&&de(e,c.fid),c}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function F(e){let t;const n=await S(e.appConfig,o=>{const i=Ue(o),r=Ge(e,i);return t=r.registrationPromise,r.installationEntry});return n.fid===D?{installationEntry:await t}:{installationEntry:n,registrationPromise:t}}function Ue(e){const t=e||{fid:qe(),registrationStatus:0};return le(t)}function Ge(e,t){if(t.registrationStatus===0){if(!navigator.onLine){const i=Promise.reject(g.create("app-offline"));return{installationEntry:t,registrationPromise:i}}const n={fid:t.fid,registrationStatus:1,registrationTime:Date.now()},o=Je(e,n);return{installationEntry:n,registrationPromise:o}}else return t.registrationStatus===1?{installationEntry:t,registrationPromise:Ye(e)}:{installationEntry:t}}async function Je(e,t){try{const n=await Fe(e,t);return k(e.appConfig,n)}catch(n){throw ne(n)&&n.customData.serverCode===409?await pe(e.appConfig):await k(e.appConfig,{fid:t.fid,registrationStatus:0}),n}}async function Ye(e){let t=await B(e.appConfig);for(;t.registrationStatus===1;)await ce(100),t=await B(e.appConfig);if(t.registrationStatus===0){const{installationEntry:n,registrationPromise:o}=await F(e);return o||n}return t}function B(e){return S(e,t=>{if(!t)throw g.create("installation-not-found");return le(t)})}function le(e){return ze(e)?{fid:e.fid,registrationStatus:0}:e}function ze(e){return e.registrationStatus===1&&e.registrationTime+Z<Date.now()}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Xe({appConfig:e,heartbeatServiceProvider:t},n){const o=Qe(e,n),i=Pe(e,n),r=t.getImmediate({optional:!0});if(r){const d=await r.getHeartbeatsHeader();d&&i.append("x-firebase-client",d)}const a={installation:{sdkVersion:ee,appId:e.appId}},c={method:"POST",headers:i,body:JSON.stringify(a)},f=await se(()=>fetch(o,c));if(f.ok){const d=await f.json();return ie(d)}else throw await re("Generate Auth Token",f)}function Qe(e,{fid:t}){return`${oe(e)}/${t}/authTokens:generate`}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function K(e,t=!1){let n;const o=await S(e.appConfig,r=>{if(!ge(r))throw g.create("not-registered");const a=r.authToken;if(!t&&tt(a))return r;if(a.requestStatus===1)return n=Ze(e,t),r;{if(!navigator.onLine)throw g.create("app-offline");const c=ot(r);return n=et(e,c),c}});return n?await n:o.authToken}async function Ze(e,t){let n=await H(e.appConfig);for(;n.authToken.requestStatus===1;)await ce(100),n=await H(e.appConfig);const o=n.authToken;return o.requestStatus===0?K(e,t):o}function H(e){return S(e,t=>{if(!ge(t))throw g.create("not-registered");const n=t.authToken;return it(n)?Object.assign(Object.assign({},t),{authToken:{requestStatus:0}}):t})}async function et(e,t){try{const n=await Xe(e,t),o=Object.assign(Object.assign({},t),{authToken:n});return await k(e.appConfig,o),n}catch(n){if(ne(n)&&(n.customData.serverCode===401||n.customData.serverCode===404))await pe(e.appConfig);else{const o=Object.assign(Object.assign({},t),{authToken:{requestStatus:0}});await k(e.appConfig,o)}throw n}}function ge(e){return e!==void 0&&e.registrationStatus===2}function tt(e){return e.requestStatus===2&&!nt(e)}function nt(e){const t=Date.now();return t<e.creationTime||e.creationTime+e.expiresIn<t+Ce}function ot(e){const t={requestStatus:1,requestTime:Date.now()};return Object.assign(Object.assign({},e),{authToken:t})}function it(e){return e.requestStatus===1&&e.requestTime+Z<Date.now()}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function rt(e){const t=e,{installationEntry:n,registrationPromise:o}=await F(t);return o?o.catch(console.error):K(t).catch(console.error),n.fid}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function at(e,t=!1){const n=e;return await st(n),(await K(n,t)).token}async function st(e){const{registrationPromise:t}=await F(e);t&&await t}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function ct(e){if(!e||!e.options)throw _("App Configuration");if(!e.name)throw _("App Name");const t=["projectId","apiKey","appId"];for(const n of t)if(!e.options[n])throw _(n);return{appName:e.name,projectId:e.options.projectId,apiKey:e.options.apiKey,appId:e.options.appId}}function _(e){return g.create("missing-app-config-values",{valueName:e})}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const we="installations",ut="installations-internal",dt=e=>{const t=e.getProvider("app").getImmediate(),n=ct(t),o=M(t,"heartbeat");return{app:t,appConfig:n,heartbeatServiceProvider:o,_delete:()=>Promise.resolve()}},ft=e=>{const t=e.getProvider("app").getImmediate(),n=M(t,we).getImmediate();return{getId:()=>rt(n),getToken:i=>at(n,i)}};function pt(){m(new T(we,dt,"PUBLIC")),m(new T(ut,ft,"PRIVATE"))}pt();y(Q,R);y(Q,R,"esm2017");/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const lt="/firebase-messaging-sw.js",gt="/firebase-cloud-messaging-push-scope",he="BDOU99-h67HcA6JeFXHbSNMu7e2yNNu3RzoMj8TM4W88jITfq7ZmPvIM1Iv-4_l2LxQcYwhqby2xGpWwzjfAnG4",wt="https://fcmregistrations.googleapis.com/v1",be="google.c.a.c_id",ht="google.c.a.c_l",bt="google.c.a.ts",yt="google.c.a.e";var W;(function(e){e[e.DATA_MESSAGE=1]="DATA_MESSAGE",e[e.DISPLAY_NOTIFICATION=3]="DISPLAY_NOTIFICATION"})(W||(W={}));/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 * in compliance with the License. You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License
 * is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
 * or implied. See the License for the specific language governing permissions and limitations under
 * the License.
 */var b;(function(e){e.PUSH_RECEIVED="push-received",e.NOTIFICATION_CLICKED="notification-clicked"})(b||(b={}));/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function p(e){const t=new Uint8Array(e);return btoa(String.fromCharCode(...t)).replace(/=/g,"").replace(/\+/g,"-").replace(/\//g,"_")}function mt(e){const t="=".repeat((4-e.length%4)%4),n=(e+t).replace(/\-/g,"+").replace(/_/g,"/"),o=atob(n),i=new Uint8Array(o.length);for(let r=0;r<o.length;++r)i[r]=o.charCodeAt(r);return i}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const O="fcm_token_details_db",Tt=5,U="fcm_token_object_Store";async function kt(e){if("databases"in indexedDB&&!(await indexedDB.databases()).map(r=>r.name).includes(O))return null;let t=null;return(await P(O,Tt,{upgrade:async(o,i,r,a)=>{var c;if(i<2||!o.objectStoreNames.contains(U))return;const f=a.objectStore(U),d=await f.index("fcmSenderId").get(e);if(await f.clear(),!!d){if(i===2){const s=d;if(!s.auth||!s.p256dh||!s.endpoint)return;t={token:s.fcmToken,createTime:(c=s.createTime)!==null&&c!==void 0?c:Date.now(),subscriptionOptions:{auth:s.auth,p256dh:s.p256dh,endpoint:s.endpoint,swScope:s.swScope,vapidKey:typeof s.vapidKey=="string"?s.vapidKey:p(s.vapidKey)}}}else if(i===3){const s=d;t={token:s.fcmToken,createTime:s.createTime,subscriptionOptions:{auth:p(s.auth),p256dh:p(s.p256dh),endpoint:s.endpoint,swScope:s.swScope,vapidKey:p(s.vapidKey)}}}else if(i===4){const s=d;t={token:s.fcmToken,createTime:s.createTime,subscriptionOptions:{auth:p(s.auth),p256dh:p(s.p256dh),endpoint:s.endpoint,swScope:s.swScope,vapidKey:p(s.vapidKey)}}}}}})).close(),await A(O),await A("fcm_vapid_details_db"),await A("undefined"),It(t)?t:null}function It(e){if(!e||!e.subscriptionOptions)return!1;const{subscriptionOptions:t}=e;return typeof e.createTime=="number"&&e.createTime>0&&typeof e.token=="string"&&e.token.length>0&&typeof t.auth=="string"&&t.auth.length>0&&typeof t.p256dh=="string"&&t.p256dh.length>0&&typeof t.endpoint=="string"&&t.endpoint.length>0&&typeof t.swScope=="string"&&t.swScope.length>0&&typeof t.vapidKey=="string"&&t.vapidKey.length>0}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const vt="firebase-messaging-database",St=1,h="firebase-messaging-store";let C=null;function $(){return C||(C=P(vt,St,{upgrade:(e,t)=>{switch(t){case 0:e.createObjectStore(h)}}})),C}async function ye(e){const t=x(e),o=await(await $()).transaction(h).objectStore(h).get(t);if(o)return o;{const i=await kt(e.appConfig.senderId);if(i)return await q(e,i),i}}async function q(e,t){const n=x(e),i=(await $()).transaction(h,"readwrite");return await i.objectStore(h).put(t,n),await i.done,t}async function At(e){const t=x(e),o=(await $()).transaction(h,"readwrite");await o.objectStore(h).delete(t),await o.done}function x({appConfig:e}){return e.appId}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Et={"missing-app-config-values":'Missing App configuration value: "{$valueName}"',"only-available-in-window":"This method is available in a Window context.","only-available-in-sw":"This method is available in a service worker context.","permission-default":"The notification permission was not granted and dismissed instead.","permission-blocked":"The notification permission was not granted and blocked instead.","unsupported-browser":"This browser doesn't support the API's required to use the Firebase SDK.","indexed-db-unsupported":"This browser doesn't support indexedDb.open() (ex. Safari iFrame, Firefox Private Browsing, etc)","failed-service-worker-registration":"We are unable to register the default service worker. {$browserErrorMessage}","token-subscribe-failed":"A problem occurred while subscribing the user to FCM: {$errorInfo}","token-subscribe-no-token":"FCM returned no token when subscribing the user to push.","token-unsubscribe-failed":"A problem occurred while unsubscribing the user from FCM: {$errorInfo}","token-update-failed":"A problem occurred while updating the user from FCM: {$errorInfo}","token-update-no-token":"FCM returned no token when updating the user to push.","use-sw-after-get-token":"The useServiceWorker() method may only be called once and must be called before calling getToken() to ensure your service worker is used.","invalid-sw-registration":"The input to useServiceWorker() must be a ServiceWorkerRegistration.","invalid-bg-handler":"The input to setBackgroundMessageHandler() must be a function.","invalid-vapid-key":"The public VAPID key must be a string.","use-vapid-key-after-get-token":"The usePublicVapidKey() method may only be called once and must be called before calling getToken() to ensure your VAPID key is used."},u=new X("messaging","Messaging",Et);/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function _t(e,t){const n=await V(e),o=Te(t),i={method:"POST",headers:n,body:JSON.stringify(o)};let r;try{r=await(await fetch(L(e.appConfig),i)).json()}catch(a){throw u.create("token-subscribe-failed",{errorInfo:a==null?void 0:a.toString()})}if(r.error){const a=r.error.message;throw u.create("token-subscribe-failed",{errorInfo:a})}if(!r.token)throw u.create("token-subscribe-no-token");return r.token}async function Ot(e,t){const n=await V(e),o=Te(t.subscriptionOptions),i={method:"PATCH",headers:n,body:JSON.stringify(o)};let r;try{r=await(await fetch(`${L(e.appConfig)}/${t.token}`,i)).json()}catch(a){throw u.create("token-update-failed",{errorInfo:a==null?void 0:a.toString()})}if(r.error){const a=r.error.message;throw u.create("token-update-failed",{errorInfo:a})}if(!r.token)throw u.create("token-update-no-token");return r.token}async function me(e,t){const o={method:"DELETE",headers:await V(e)};try{const r=await(await fetch(`${L(e.appConfig)}/${t}`,o)).json();if(r.error){const a=r.error.message;throw u.create("token-unsubscribe-failed",{errorInfo:a})}}catch(i){throw u.create("token-unsubscribe-failed",{errorInfo:i==null?void 0:i.toString()})}}function L({projectId:e}){return`${wt}/projects/${e}/registrations`}async function V({appConfig:e,installations:t}){const n=await t.getToken();return new Headers({"Content-Type":"application/json",Accept:"application/json","x-goog-api-key":e.apiKey,"x-goog-firebase-installations-auth":`FIS ${n}`})}function Te({p256dh:e,auth:t,endpoint:n,vapidKey:o}){const i={web:{endpoint:n,auth:t,p256dh:e}};return o!==he&&(i.web.applicationPubKey=o),i}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Ct=7*24*60*60*1e3;async function Nt(e){const t=await Pt(e.swRegistration,e.vapidKey),n={vapidKey:e.vapidKey,swScope:e.swRegistration.scope,endpoint:t.endpoint,auth:p(t.getKey("auth")),p256dh:p(t.getKey("p256dh"))},o=await ye(e.firebaseDependencies);if(o){if(Rt(o.subscriptionOptions,n))return Date.now()>=o.createTime+Ct?Mt(e,{token:o.token,createTime:Date.now(),subscriptionOptions:n}):o.token;try{await me(e.firebaseDependencies,o.token)}catch(i){console.warn(i)}return G(e.firebaseDependencies,n)}else return G(e.firebaseDependencies,n)}async function Dt(e){const t=await ye(e.firebaseDependencies);t&&(await me(e.firebaseDependencies,t.token),await At(e.firebaseDependencies));const n=await e.swRegistration.pushManager.getSubscription();return n?n.unsubscribe():!0}async function Mt(e,t){try{const n=await Ot(e.firebaseDependencies,t),o=Object.assign(Object.assign({},t),{token:n,createTime:Date.now()});return await q(e.firebaseDependencies,o),n}catch(n){throw n}}async function G(e,t){const o={token:await _t(e,t),createTime:Date.now(),subscriptionOptions:t};return await q(e,o),o.token}async function Pt(e,t){const n=await e.pushManager.getSubscription();return n||e.pushManager.subscribe({userVisibleOnly:!0,applicationServerKey:mt(t)})}function Rt(e,t){const n=t.vapidKey===e.vapidKey,o=t.endpoint===e.endpoint,i=t.auth===e.auth,r=t.p256dh===e.p256dh;return n&&o&&i&&r}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function J(e){const t={from:e.from,collapseKey:e.collapse_key,messageId:e.fcmMessageId};return jt(t,e),Ft(t,e),Kt(t,e),t}function jt(e,t){if(!t.notification)return;e.notification={};const n=t.notification.title;n&&(e.notification.title=n);const o=t.notification.body;o&&(e.notification.body=o);const i=t.notification.image;i&&(e.notification.image=i);const r=t.notification.icon;r&&(e.notification.icon=r)}function Ft(e,t){t.data&&(e.data=t.data)}function Kt(e,t){var n,o,i,r,a;if(!t.fcmOptions&&!(!((n=t.notification)===null||n===void 0)&&n.click_action))return;e.fcmOptions={};const c=(i=(o=t.fcmOptions)===null||o===void 0?void 0:o.link)!==null&&i!==void 0?i:(r=t.notification)===null||r===void 0?void 0:r.click_action;c&&(e.fcmOptions.link=c);const f=(a=t.fcmOptions)===null||a===void 0?void 0:a.analytics_label;f&&(e.fcmOptions.analyticsLabel=f)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function $t(e){return typeof e=="object"&&!!e&&be in e}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function qt(e){if(!e||!e.options)throw N("App Configuration Object");if(!e.name)throw N("App Name");const t=["projectId","apiKey","appId","messagingSenderId"],{options:n}=e;for(const o of t)if(!n[o])throw N(o);return{appName:e.name,projectId:n.projectId,apiKey:n.apiKey,appId:n.appId,senderId:n.messagingSenderId}}function N(e){return u.create("missing-app-config-values",{valueName:e})}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */class xt{constructor(t,n,o){this.deliveryMetricsExportedToBigQueryEnabled=!1,this.onBackgroundMessageHandler=null,this.onMessageHandler=null,this.logEvents=[],this.isLogServiceStarted=!1;const i=qt(t);this.firebaseDependencies={app:t,appConfig:i,installations:n,analyticsProvider:o}}_delete(){return Promise.resolve()}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function ke(e){try{e.swRegistration=await navigator.serviceWorker.register(lt,{scope:gt}),e.swRegistration.update().catch(()=>{})}catch(t){throw u.create("failed-service-worker-registration",{browserErrorMessage:t==null?void 0:t.message})}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Lt(e,t){if(!t&&!e.swRegistration&&await ke(e),!(!t&&e.swRegistration)){if(!(t instanceof ServiceWorkerRegistration))throw u.create("invalid-sw-registration");e.swRegistration=t}}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Vt(e,t){t?e.vapidKey=t:e.vapidKey||(e.vapidKey=he)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Ie(e,t){if(!navigator)throw u.create("only-available-in-window");if(Notification.permission==="default"&&await Notification.requestPermission(),Notification.permission!=="granted")throw u.create("permission-blocked");return await Vt(e,t==null?void 0:t.vapidKey),await Lt(e,t==null?void 0:t.serviceWorkerRegistration),Nt(e)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Bt(e,t,n){const o=Ht(t);(await e.firebaseDependencies.analyticsProvider.get()).logEvent(o,{message_id:n[be],message_name:n[ht],message_time:n[bt],message_device_time:Math.floor(Date.now()/1e3)})}function Ht(e){switch(e){case b.NOTIFICATION_CLICKED:return"notification_open";case b.PUSH_RECEIVED:return"notification_foreground";default:throw new Error}}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Wt(e,t){const n=t.data;if(!n.isFirebaseMessaging)return;e.onMessageHandler&&n.messageType===b.PUSH_RECEIVED&&(typeof e.onMessageHandler=="function"?e.onMessageHandler(J(n)):e.onMessageHandler.next(J(n)));const o=n.data;$t(o)&&o[yt]==="1"&&await Bt(e,n.messageType,o)}const Y="@firebase/messaging",z="0.12.12";/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */const Ut=e=>{const t=new xt(e.getProvider("app").getImmediate(),e.getProvider("installations-internal").getImmediate(),e.getProvider("analytics-internal"));return navigator.serviceWorker.addEventListener("message",n=>Wt(t,n)),t},Gt=e=>{const t=e.getProvider("messaging").getImmediate();return{getToken:o=>Ie(t,o)}};function Jt(){m(new T("messaging",Ut,"PUBLIC")),m(new T("messaging-internal",Gt,"PRIVATE")),y(Y,z),y(Y,z,"esm2017")}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function Yt(){try{await Ae()}catch{return!1}return typeof window<"u"&&Ee()&&_e()&&"serviceWorker"in navigator&&"PushManager"in window&&"Notification"in window&&"fetch"in window&&ServiceWorkerRegistration.prototype.hasOwnProperty("showNotification")&&PushSubscription.prototype.hasOwnProperty("getKey")}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */async function zt(e){if(!navigator)throw u.create("only-available-in-window");return e.swRegistration||await ke(e),Dt(e)}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Xt(e,t){if(!navigator)throw u.create("only-available-in-window");return e.onMessageHandler=t,()=>{e.onMessageHandler=null}}/**
 * @license
 * Copyright 2017 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */function Zt(e=Se()){return Yt().then(t=>{if(!t)throw u.create("unsupported-browser")},t=>{throw u.create("indexed-db-unsupported")}),M(I(e),"messaging").getImmediate()}async function en(e,t){return e=I(e),Ie(e,t)}function tn(e){return e=I(e),zt(e)}function nn(e,t){return e=I(e),Xt(e,t)}Jt();export{tn as deleteToken,Zt as getMessaging,en as getToken,Yt as isSupported,nn as onMessage};
