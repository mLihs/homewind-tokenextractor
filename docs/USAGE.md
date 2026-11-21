# Using Homewind Token Extractor

This app is a helper app for [Homewind](https://homewind.io). It adds Xiaomi fans to Homewind with one click, or it gets the fan token so you can add a fan to Homewind manually.

Homewind must already be on your Wi-Fi. The app does not set up Homewind's Wi-Fi. Phone and Homewind need to be on a network that allows device-to-device traffic. A guest network or client isolation hides Homewind from the search.

## First launch

Download the build for your system from a [GitHub Actions](../.github/workflows/build.yml) run or from a GitHub Release (`v*`).

On macOS the app is not signed with an Apple developer certificate. The first time you open a new build, right-click `HomewindTokenExtractor.app`, choose **Open**, then **Open** again. A normal double-click is blocked.

The first time you click **Add to Homewind**, macOS asks for permission to find devices on the local network. Allow it. The search does not run when the app starts, only when you click. On Windows the firewall may ask the same question the first time.

## Sign in

Choose **Email** or **QR code**.

Email takes the Xiaomi Home account (email, phone, or Xiaomi ID) and the password. Xiaomi sometimes asks for the characters in a picture, or for a code sent to your email. The password is not saved. **Cancel** on the waiting screen returns to the sign-in form.

QR code shows a code after **Show QR code**. In the Xiaomi Home app, open the scan icon and confirm the sign-in on the phone. An unused code expires; start it again.

After a successful sign-in the app looks through Xiaomi's regions and shows **Looking for your fans … n/8**. If Xiaomi accepts the connection and then stays silent, the request stops after 20 seconds and the app shows **Xiaomi did not answer. Try again.**

## Your fans

The list contains only fans Homewind can control. Each tile shows the name from Xiaomi Home, the product name when the model is known, and two actions:

- **Copy token** puts the 32-character token on the clipboard. The button shows **Copied** for a moment.
- **Add to Homewind** sends that token to a Homewind on the network.

The two icons at the top right are **Reload fans** (circular arrows) and **Sign out** (arrow out of a door). Point at an icon to see its name.

**Reload fans** asks Xiaomi for the list again with the same sign-in. It does not ask for the password again. **Cancel** on that waiting screen returns to the list you already had. The button is disabled while a fan is being added. If Xiaomi has ended the sign-in in the meantime, the app goes back to the sign-in page and shows **Xiaomi ended the sign-in. Sign in again.**

**Sign out** drops the Xiaomi session and clears the password field. It does not forget the last Homewind (see below).

If your fan is missing, it is either not in this Xiaomi account or its model is not one Homewind controls. The empty state links to the Homewind issue tracker; include the model id from the Xiaomi app.

## Add to Homewind

Homewind and this computer must be on the same LAN. The app looks for hosts whose name starts with `homewind-`, then checks `GET /api/v1/system/info` for `name=Homewind` and `ready=1`.

1. If you have added a fan before, that Homewind is tried first. When it answers, the token is sent there and no list is shown, even if other Homewinds are on the network.
2. Otherwise the app searches for a few seconds. One Homewind is used immediately. More than one opens **Choose a Homewind**. The label looks like `Homewind a1b2c3d4 · 192.168.1.40`. The choice is remembered.
3. None found opens **Homewind not found**. **Search again** tries once more. **Use this address** takes an IP address or a hostname such as `homewind-a1b2c3d4.local`.

A successful add changes the button to **Added**. Sending the same token again is fine: Homewind accepts it and does not take a second slot.

The red line on the tile is the failure:

| Message | What it means |
| --- | --- |
| Homewind not reachable | The saved or chosen Homewind did not answer. The saved address is forgotten and the app searches again. |
| Token not accepted | The token is not 32 hex characters, or Homewind rejected it. |
| Homewind is full (4/4) | Four fans are already stored. Firmware that still reports "full" as a generic failure shows **Homewind refused the request** instead. |
| Homewind is updating, try again later | Homewind is in maintenance. |
| Homewind is starting, try again in a moment | Homewind is up but not ready. |
| Homewind firmware too old or not a Homewind | The device answered, but it is not a Homewind that accepts this request. |
| Homewind refused the request | Homewind returned another error. |

**Cancel** in the search dialog leaves the tile on **Add to Homewind**.

## What is stored

The password is not stored. The Xiaomi session lives only until you sign out or quit the app.

The last Homewind is stored in the app settings: host, hostname, and IP address. That is why the next **Add to Homewind** skips the picker when that device still answers. Nothing else about the fans is written to disk.

## When something fails

**The app will not open on macOS.** Right-click the new build and choose **Open**. Each rebuild has a new signature, so the exception from the previous build does not carry over.

**Sign-in sits on "Signing in …" and then says Xiaomi did not answer.** Try again. A picture check or an email code, if Xiaomi asks for one, appears as a dialog; it is not the same as a hang.

**The fan list is empty but the Xiaomi app shows fans.** Those fans are in the account, but their model is not one of the prefixes `dmaker.fan.`, `zhimi.fan.`, or `xiaomi.fan.`, or the model is marked `enabled: false` in the catalog (`dmaker.fan.1c`).

**Search says Homewind was not found, Search again finds it.** Allow local network access if macOS asked, then search again. You can also type the IP address from the Homewind web UI. The Homewind must not still be in Wi-Fi setup mode.

**The wrong Homewind receives the fan.** The app reuses the last one that answered. Add the fan from a machine that can reach the Homewind you want, or wait until the saved one is offline so the search runs again and you can pick another.
