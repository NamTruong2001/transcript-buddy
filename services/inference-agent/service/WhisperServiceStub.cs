using System;
using System.Diagnostics;
using System.IO;
using System.ServiceProcess;
using System.Threading;

public class TranscriptWhisperService : ServiceBase
{
    private Process child;
    private readonly string agentDir;
    private readonly string python;
    private readonly string envFile;
    private readonly string logDir;

    public TranscriptWhisperService()
    {
        this.ServiceName = "TranscriptWhisper";
        this.CanStop = true;
        this.CanShutdown = true;
        this.AutoLog = true;
        agentDir = Environment.GetEnvironmentVariable("TB_AGENT_DIR");
        if (string.IsNullOrEmpty(agentDir))
            agentDir = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, ".."));
        python = Environment.GetEnvironmentVariable("TB_PYTHON");
        if (string.IsNullOrEmpty(python))
            python = Path.GetFullPath(Path.Combine(agentDir, "..", "..", ".venv", "Scripts", "python.exe"));
        envFile = Path.Combine(agentDir, "service", "service.env");
        logDir = Path.Combine(agentDir, "logs");
    }

    protected override void OnStart(string[] args)
    {
        Directory.CreateDirectory(logDir);
        var psi = new ProcessStartInfo();
        psi.FileName = python;
        psi.Arguments = "-m uvicorn app.main:app --host " + GetEnv("AGENT_HOST", "0.0.0.0") +
                        " --port " + GetEnv("AGENT_PORT", "8100");
        psi.WorkingDirectory = agentDir;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;

        // Base env
        psi.EnvironmentVariables["PYTHONPATH"] = agentDir + ";" + Path.GetFullPath(Path.Combine(agentDir, "..", "..", "src"));
        LoadEnvFile(psi, envFile);
        if (!psi.EnvironmentVariables.ContainsKey("MODELS_DIR") || string.IsNullOrEmpty(psi.EnvironmentVariables["MODELS_DIR"]))
            psi.EnvironmentVariables["MODELS_DIR"] = Path.GetFullPath(Path.Combine(agentDir, "..", "..", "models", "faster-whisper"));

        child = new Process();
        child.StartInfo = psi;
        child.OutputDataReceived += (s, e) => { if (e.Data != null) File.AppendAllText(Path.Combine(logDir, "service-stdout.log"), e.Data + Environment.NewLine); };
        child.ErrorDataReceived += (s, e) => { if (e.Data != null) File.AppendAllText(Path.Combine(logDir, "service-stderr.log"), e.Data + Environment.NewLine); };
        child.Start();
        child.BeginOutputReadLine();
        child.BeginErrorReadLine();
        File.AppendAllText(Path.Combine(logDir, "service-stdout.log"), DateTime.Now.ToString("s") + " service started pid=" + child.Id + Environment.NewLine);
    }

    protected override void OnStop()
    {
        try
        {
            if (child != null && !child.HasExited)
            {
                child.Kill();
                child.WaitForExit(10000);
            }
        }
        catch (Exception ex)
        {
            File.AppendAllText(Path.Combine(logDir, "service-stderr.log"), "stop error: " + ex.Message + Environment.NewLine);
        }
    }

    private static string GetEnv(string key, string fallback)
    {
        var v = Environment.GetEnvironmentVariable(key);
        return string.IsNullOrEmpty(v) ? fallback : v;
    }

    private static void LoadEnvFile(ProcessStartInfo psi, string path)
    {
        if (!File.Exists(path)) return;
        foreach (var raw in File.ReadAllLines(path))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#") || line.IndexOf('=') < 0) continue;
            var i = line.IndexOf('=');
            var k = line.Substring(0, i).Trim();
            var v = line.Substring(i + 1).Trim();
            psi.EnvironmentVariables[k] = v;
        }
    }

    public static void Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--console")
        {
            var svc = new TranscriptWhisperService();
            svc.OnStart(args);
            Console.WriteLine("Running in console. Ctrl+C to stop.");
            Thread.Sleep(Timeout.Infinite);
            return;
        }
        ServiceBase.Run(new TranscriptWhisperService());
    }
}
