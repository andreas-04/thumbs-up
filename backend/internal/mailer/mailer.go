// Package mailer sends the transactional emails (invite, approval,
// revocation) using only the standard library: net/smtp plus a
// hand-assembled MIME message. Certificates are never attached — emails
// carry a one-time claim link instead.
package mailer

import (
	"crypto/tls"
	"errors"
	"fmt"
	"mime"
	"net"
	"net/smtp"
	"strconv"
	"strings"

	"github.com/andreas-04/terra-crate/backend/internal/store"
)

// Send delivers an email using the SMTP configuration in settings.
// use_tls=true means STARTTLS (typically port 587); false means implicit TLS
// (SMTPS, typically port 465).
func Send(settings *store.SystemSettings, to, subject, bodyHTML, bodyText string) error {
	if settings == nil || !settings.SMTPEnabled {
		return errors.New("SMTP is not enabled")
	}
	host := strings.TrimSpace(settings.SMTPHost)
	if host == "" {
		return errors.New("SMTP host is not configured")
	}
	from := strings.TrimSpace(settings.SMTPFromEmail)
	if from == "" {
		from = strings.TrimSpace(settings.SMTPUsername)
	}
	if from == "" {
		return errors.New("SMTP from-email is not configured")
	}
	port := settings.SMTPPort
	if port == 0 {
		port = 587
	}
	addr := net.JoinHostPort(host, strconv.Itoa(port))

	msg := buildMessage(from, to, subject, bodyHTML, bodyText)

	var client *smtp.Client
	var err error
	if settings.SMTPUseTLS {
		client, err = smtp.Dial(addr)
		if err != nil {
			return err
		}
		if err = client.StartTLS(&tls.Config{ServerName: host}); err != nil {
			client.Close()
			return err
		}
	} else {
		conn, derr := tls.Dial("tcp", addr, &tls.Config{ServerName: host})
		if derr != nil {
			return derr
		}
		client, err = smtp.NewClient(conn, host)
		if err != nil {
			conn.Close()
			return err
		}
	}
	defer client.Close()

	if username := strings.TrimSpace(settings.SMTPUsername); username != "" {
		if err := client.Auth(smtp.PlainAuth("", username, settings.SMTPPassword, host)); err != nil {
			return err
		}
	}
	if err := client.Mail(from); err != nil {
		return err
	}
	if err := client.Rcpt(to); err != nil {
		return err
	}
	w, err := client.Data()
	if err != nil {
		return err
	}
	if _, err := w.Write(msg); err != nil {
		return err
	}
	if err := w.Close(); err != nil {
		return err
	}
	return client.Quit()
}

func buildMessage(from, to, subject, bodyHTML, bodyText string) []byte {
	boundary := "terracrate-alt-boundary"
	var b strings.Builder
	b.WriteString("From: " + from + "\r\n")
	b.WriteString("To: " + to + "\r\n")
	b.WriteString("Subject: " + mime.QEncoding.Encode("utf-8", subject) + "\r\n")
	b.WriteString("MIME-Version: 1.0\r\n")
	b.WriteString("Content-Type: multipart/alternative; boundary=\"" + boundary + "\"\r\n\r\n")

	b.WriteString("--" + boundary + "\r\n")
	b.WriteString("Content-Type: text/plain; charset=\"utf-8\"\r\n\r\n")
	b.WriteString(bodyText + "\r\n")
	b.WriteString("--" + boundary + "\r\n")
	b.WriteString("Content-Type: text/html; charset=\"utf-8\"\r\n\r\n")
	b.WriteString(bodyHTML + "\r\n")
	b.WriteString("--" + boundary + "--\r\n")
	return []byte(b.String())
}

// SendInviteEmail notifies a user that an account was created for them; the
// claim link downloads their certificate and shows the temporary password.
func SendInviteEmail(settings *store.SystemSettings, userEmail, deviceName, claimURL string) error {
	subject := fmt.Sprintf("You've been invited to %s", deviceName)
	text := fmt.Sprintf("An account has been created for you on %s.\n\n"+
		"Open the link below to download your access certificate and temporary\n"+
		"login password. The link works once and expires in 7 days:\n\n"+
		"  %s\n\n"+
		"You will be asked to set a new password on first login.\n", deviceName, claimURL)
	html := fmt.Sprintf("<h2>You're Invited</h2>"+
		"<p>An account has been created for you on <strong>%s</strong>.</p>"+
		"<p>Open the link below to download your access certificate and temporary "+
		"login password. The link works once and expires in 7 days:</p>"+
		"<p><a href=%q>%s</a></p>"+
		"<p>You will be asked to set a new password on first login.</p>",
		deviceName, claimURL, claimURL)
	return Send(settings, userEmail, subject, html, text)
}

// SendApprovalEmail notifies a user their account was approved; the claim
// link downloads the certificate that unlocks protected files.
func SendApprovalEmail(settings *store.SystemSettings, userEmail, deviceName, claimURL string) error {
	subject := fmt.Sprintf("Your account on %s has been approved", deviceName)
	text := fmt.Sprintf("Good news! Your account (%s) on %s has been approved.\n\n"+
		"Open the link below to download your access certificate. The link works\n"+
		"once and expires in 7 days:\n\n"+
		"  %s\n\n"+
		"Install the certificate on your device to access protected files.\n",
		userEmail, deviceName, claimURL)
	html := fmt.Sprintf("<h2>Account Approved</h2>"+
		"<p>Good news! Your account (<strong>%s</strong>) on <strong>%s</strong> has been approved.</p>"+
		"<p>Open the link below to download your access certificate. The link works "+
		"once and expires in 7 days:</p>"+
		"<p><a href=%q>%s</a></p>"+
		"<p>Install the certificate on your device to access protected files.</p>",
		userEmail, deviceName, claimURL, claimURL)
	return Send(settings, userEmail, subject, html, text)
}

// SendRevocationEmail notifies a user their certificate was revoked.
func SendRevocationEmail(settings *store.SystemSettings, userEmail, deviceName, reason string) error {
	if reason == "" {
		reason = "Your certificate has been revoked by an administrator."
	}
	subject := fmt.Sprintf("Certificate revoked on %s", deviceName)
	text := fmt.Sprintf("Your client certificate for %s has been revoked.\n\n"+
		"Reason: %s\n\n"+
		"You will no longer be able to access protected files until a new certificate is issued.\n"+
		"Please contact your administrator for a replacement certificate.\n", deviceName, reason)
	html := fmt.Sprintf("<h2>Certificate Revoked</h2>"+
		"<p>Your client certificate for <strong>%s</strong> has been revoked.</p>"+
		"<p><strong>Reason:</strong> %s</p>"+
		"<p>You will no longer be able to access protected files until a new certificate is issued.</p>"+
		"<p>Please contact your administrator for a replacement certificate.</p>", deviceName, reason)
	return Send(settings, userEmail, subject, html, text)
}
