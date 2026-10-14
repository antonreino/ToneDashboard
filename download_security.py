"""Public HTTP downloads with per-hop DNS validation and pinned connections."""
import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit, urljoin


class UnsafeDownload(ValueError):
    pass


def validate_url(url):
    try:
        parsed = urlsplit(url)
        if (len(url) > 8192 or re.search(r'[\x00-\x20\x7f\\]', url)
                or parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError()
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        if port not in (80, 443):
            raise ValueError()
        host = parsed.hostname.encode('idna').decode('ascii')
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(row[4][0] for row in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global
                          or ipaddress.ip_address(ip).is_multicast
                          or ipaddress.ip_address(ip).is_reserved
                          or getattr(ipaddress.ip_address(ip), 'sixtofour', None) is not None
                          or getattr(ipaddress.ip_address(ip), 'teredo', None) is not None
                          or (getattr(ipaddress.ip_address(ip), 'ipv4_mapped', None) is not None)
                          for ip in ips):
            raise ValueError()
        return parsed, host, port, ips
    except (ValueError, UnicodeError, OSError):
        raise UnsafeDownload('La descarga debe usar HTTP/HTTPS y un destino público en el puerto 80 o 443.') from None


def open_public(url, method='GET', headers=None):
    """Follow at most five redirects; the socket uses only a validated IP."""
    for hop in range(6):
        parsed, host, port, ips = validate_url(url)
        connection = http.client.HTTPConnection(host, port, timeout=30)
        try:
            for ip in ips:
                try:
                    sock = socket.create_connection((ip, port), timeout=30)
                    break
                except OSError:
                    if ip == ips[-1]:
                        raise
            connection.sock = sock
            if parsed.scheme == 'https':
                connection.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                response.close()
                connection.close()
                if not location or hop == 5:
                    raise UnsafeDownload('Redirección de descarga inválida o excesiva.')
                destination = urljoin(url, location)
                if parsed.scheme == 'https' and urlsplit(destination).scheme != 'https':
                    raise UnsafeDownload('No se permite redirigir HTTPS a HTTP.')
                url = destination
                continue
            response.public_url = url
            response.public_connection = connection
            return response
        except BaseException:
            connection.close()
            raise


def close_public(response):
    response.close()
    response.public_connection.close()


def download_public(url, target, resume=True):
    offset = target.stat().st_size if resume and target.exists() else 0
    headers = {'Accept-Encoding': 'identity'}
    if offset:
        headers['Range'] = f'bytes={offset}-'
    response = open_public(url, headers=headers)
    try:
        if response.status not in (200, 206):
            raise OSError(f'HTTP {response.status} en la descarga')
        if response.status == 206:
            match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+|\*)', response.getheader('Content-Range', ''))
            if not match or int(match[1]) != offset:
                raise OSError('Respuesta parcial incompatible con la reanudación')
        if response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
            raise OSError('Codificación de descarga no compatible')
        mode = 'ab' if offset and response.status == 206 else 'wb'
        remaining = response.getheader('Content-Length')
        expected = int(remaining) if remaining is not None else None
        received = 0
        with target.open(mode) as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                received += len(block)
        if expected is not None and received != expected:
            raise OSError('Descarga incompleta')
        if response.status == 206 and (match[3] == '*' or target.stat().st_size != int(match[3])):
            raise OSError('La respuesta parcial no completa el archivo')
    finally:
        close_public(response)
