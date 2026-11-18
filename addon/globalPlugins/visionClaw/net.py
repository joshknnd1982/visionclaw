# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - resumable, verified downloads. No NVDA dependencies.

import ctypes
import hashlib
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "VisionClaw"
_BLOCK = 1 << 20


class Cancelled(Exception):
	pass


def _isCertError(e):
	reason = getattr(e, "reason", e)
	return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
	def redirect_request(self, *args, **kwargs):
		return None


def _hostsFor(url, hops=5):
	"""The hosts a download passes through (GitHub redirects to a separate asset server).
	Uses an unverified connection only to read redirect locations; no data is trusted or kept."""
	hosts = []
	ctx = ssl._create_unverified_context()
	opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect)
	for _ in range(hops):
		parts = urllib.parse.urlsplit(url)
		if parts.scheme != "https" or not parts.hostname:
			break
		if (parts.hostname, parts.port or 443) not in hosts:
			hosts.append((parts.hostname, parts.port or 443))
		try:
			req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
			with opener.open(req, timeout=20):
				break
		except urllib.error.HTTPError as e:
			location = e.headers.get("Location")
			if e.code not in (301, 302, 303, 307, 308) or not location:
				break
			url = urllib.parse.urljoin(url, location)
		except Exception:
			break
	return hosts


class _CERT_ENHKEY_USAGE(ctypes.Structure):
	_fields_ = [("cUsageIdentifier", ctypes.c_ulong), ("rgpszUsageIdentifier", ctypes.c_void_p)]


class _CERT_USAGE_MATCH(ctypes.Structure):
	_fields_ = [("dwType", ctypes.c_ulong), ("Usage", _CERT_ENHKEY_USAGE)]


class _CERT_CHAIN_PARA(ctypes.Structure):
	_fields_ = [("cbSize", ctypes.c_ulong), ("RequestedUsage", _CERT_USAGE_MATCH)]


def _refreshWindowsRoots(url):
	"""Windows installs many root certificates only when something first asks for them, and
	Python can't trigger that. Asking Windows to build each server's certificate chain makes it
	fetch the missing root, after which normal (verified) connections work. NVDA does the same
	for its own update check."""
	if sys.platform != "win32":
		return False
	crypt32 = ctypes.windll.crypt32
	crypt32.CertCreateCertificateContext.restype = ctypes.c_void_p
	crypt32.CertCreateCertificateContext.argtypes = [ctypes.c_ulong, ctypes.c_char_p, ctypes.c_ulong]
	crypt32.CertGetCertificateChain.argtypes = [
		ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
		ctypes.POINTER(_CERT_CHAIN_PARA), ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
	crypt32.CertFreeCertificateChain.argtypes = [ctypes.c_void_p]
	crypt32.CertFreeCertificateContext.argtypes = [ctypes.c_void_p]
	ctx = ssl._create_unverified_context()
	refreshed = False
	for host, port in _hostsFor(url):
		try:
			with socket.create_connection((host, port), timeout=20) as raw:
				with ctx.wrap_socket(raw, server_hostname=host) as s:
					der = s.getpeercert(True)
		except OSError:
			continue
		cert = crypt32.CertCreateCertificateContext(1, der, len(der))  # X509_ASN_ENCODING
		if not cert:
			continue
		chain = ctypes.c_void_p()
		para = _CERT_CHAIN_PARA(cbSize=ctypes.sizeof(_CERT_CHAIN_PARA))
		if crypt32.CertGetCertificateChain(None, cert, None, None, ctypes.byref(para), 0, None, ctypes.byref(chain)):
			crypt32.CertFreeCertificateChain(chain)
			refreshed = True
		crypt32.CertFreeCertificateContext(cert)
	return refreshed


def _open(req, timeout):
	"""urlopen that, on a certificate error, gets Windows to install the missing root and retries once."""
	try:
		return urllib.request.urlopen(req, timeout=timeout)
	except (urllib.error.URLError, ssl.SSLError) as e:
		if not _isCertError(e):
			raise
		try:
			refreshed = _refreshWindowsRoots(req.full_url)
		except Exception:
			refreshed = False
		if not refreshed:
			raise
		# A new connection builds a fresh SSL context, which re-reads the Windows store.
		return urllib.request.urlopen(req, timeout=timeout)


def fetchJson(url, timeout=20, limit=None):
	"""Read a small JSON file from an address. limit: the most bytes it may have; a longer answer is refused."""
	req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
	with _open(req, timeout) as r:
		body = r.read() if limit is None else r.read(limit + 1)
	if limit is not None and len(body) > limit:
		raise ValueError("The answer is longer than it may be.")
	return json.loads(body.decode("utf-8"))


def fetchText(url, timeout=30, limit=None, hosts=None, agent=None, textOnly=False):
	"""Read a text from an address. limit: the most bytes it may have. hosts: the only servers the answer may
	come from, also after a redirect; anything else is refused. agent: what the request calls itself, where
	a server asks for more than a name. textOnly: refuse an answer that is not text, such as a picture or a
	program, before any of it is read."""
	req = urllib.request.Request(url, headers={"User-Agent": agent or USER_AGENT, "Cache-Control": "no-cache"})
	with _open(req, timeout) as r:
		host = urllib.parse.urlsplit(r.geturl()).hostname or ""
		if hosts is not None and host not in hosts:
			raise ValueError("The answer came from a place it may not come from.")
		kind = (r.headers.get("Content-Type") or "").lower()
		if textOnly and kind and not kind.startswith("text/") and not any(word in kind for word in ("html", "json", "xml")):
			raise ValueError("The answer is not text.")
		body = r.read() if limit is None else r.read(limit + 1)
	if limit is not None and len(body) > limit:
		raise ValueError("The answer is longer than it may be.")
	return body.decode("utf-8", "replace")


def download(url, dest, size=None, sha256=None, onProgress=None, cancel=None):
	"""Download url to dest, resuming from dest + '.part' if a previous attempt was interrupted.
	Calls onProgress(doneBytes, totalBytes). Raises Cancelled, OSError, or ValueError if the file is corrupt."""
	part = dest + ".part"
	digest = hashlib.sha256()
	done = 0
	if os.path.isfile(part):
		# Re-hash what we already have so the final checksum covers the whole file.
		with open(part, "rb") as f:
			for block in iter(lambda: f.read(_BLOCK), b""):
				digest.update(block)
				done += len(block)
		if size and done > size:
			os.remove(part)
			digest, done = hashlib.sha256(), 0
	headers = {"User-Agent": USER_AGENT}
	if done:
		headers["Range"] = f"bytes={done}-"
	if not (size and done == size):
		with _open(urllib.request.Request(url, headers=headers), 60) as r:
			if done and r.status != 206:
				# Server ignored the range request; start again.
				digest, done = hashlib.sha256(), 0
				mode = "wb"
			else:
				mode = "ab" if done else "wb"
			total = size or (done + int(r.headers.get("Content-Length") or 0)) or None
			with open(part, mode) as f:
				while True:
					if cancel is not None and cancel.is_set():
						raise Cancelled()
					block = r.read(_BLOCK)
					if not block:
						break
					f.write(block)
					digest.update(block)
					done += len(block)
					if onProgress is not None:
						onProgress(done, total)
	if size and done != size:
		raise OSError(f"Download incomplete: got {done} of {size} bytes.")
	if sha256 and digest.hexdigest().lower() != sha256.lower():
		os.remove(part)
		raise ValueError("The downloaded file is damaged. Please try again.")
	os.replace(part, dest)
	return dest
