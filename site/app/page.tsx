import catalog from "../catalog.json";
import { CopyCommand } from "./copy-command";

const repo = "https://github.com/ammar-hasan/agent-skills";

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header wrap">
        <a className="brand" href="/agent-skills/" aria-label="Agent Skills home">
          <span className="brand-mark" aria-hidden="true">
            as<span>_</span>
          </span>
          <span>Agent Skills</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#catalog">Catalog</a>
          <a href="#getting-started">Get started</a>
          <a href={repo}>
            GitHub <span aria-hidden="true">↗</span>
          </a>
        </nav>
      </header>
      <main id="main">
        <section className="hero wrap">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="status-dot" /> A small, considered collection
            </p>
            <h1>
              Good workflows.
              <br />
              <em>Shared as skills.</em>
            </h1>
            <p className="hero-description">
              Practical instructions and tools for AI agents. Selected from real
              work, easy to read, and ready to make your own.
            </p>
            <div className="hero-actions">
              <a className="button primary" href="#catalog">
                Explore the catalog <span aria-hidden="true">↓</span>
              </a>
              <a className="text-link" href={`${repo}/blob/main/README.md`}>
                Read the introduction <span aria-hidden="true">↗</span>
              </a>
            </div>
            <div className="hero-facts">
              <span>Open source</span>
              <span>MIT licensed</span>
              <span>Agent Skills format</span>
            </div>
          </div>
          <aside className="field-note" aria-label="About this collection">
            <div className="note-top">
              <span>FIELD NOTES / 001</span>
              <span aria-hidden="true">↗</span>
            </div>
            <div className="sheet-stack" aria-hidden="true">
              <div className="sheet back" />
              <div className="sheet middle" />
              <div className="sheet front">
                <span>SKILL.md</span>
                <i />
                <i />
                <i />
                <b>
                  instructions
                  <br />
                  with a purpose.
                </b>
                <span className="sheet-plus">+</span>
              </div>
            </div>
            <h2>
              A useful workflow,
              <br />
              written down.
            </h2>
            <p>
              A skill gives an agent the context and steps to do a specific job
              well. Take the ones that fit your work.
            </p>
            <div className="note-bottom">
              <span>CURATED BY AMMAR HASAN</span>
              <span>01—</span>
            </div>
          </aside>
        </section>
        <section className="catalog-section" id="catalog">
          <div className="wrap">
            <div className="section-heading">
              <div>
                <p className="eyebrow">The collection</p>
                <h2>Skills with a job to do.</h2>
              </div>
              <span className="count">
                {String(catalog.length).padStart(2, "0")}{" "}
                {catalog.length === 1 ? "skill" : "skills"} available
              </span>
            </div>
            {catalog.map((skill, index) => (
              <article className="skill-card" key={skill.name} id={skill.name}>
                <div className="skill-overview">
                  <div className="card-kicker">
                    <span className="skill-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="tag">{skill.category}</span>
                  </div>
                  <h3>{skill.title}</h3>
                  <p className="skill-summary">{skill.summary}</p>
                  <ul className="features">
                    {skill.features.map((feature) => (
                      <li key={feature}>
                        <span aria-hidden="true">↳</span>
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <a
                    className="text-link"
                    href={`${repo}/tree/main/skills/${skill.name}`}
                  >
                    Explore the skill <span aria-hidden="true">↗</span>
                  </a>
                </div>
                <div className="skill-details">
                  <p className="eyebrow">When to reach for it</p>
                  <p>{skill.useWhen}</p>
                  <div className="requirements" aria-label="Requirements">
                    {skill.requirements.map((requirement) => (
                      <span key={requirement}>{requirement}</span>
                    ))}
                  </div>
                  <div className="install-box">
                    <span className="eyebrow">Add to your toolkit</span>
                    <CopyCommand
                      command={`npx skills add ammar-hasan/agent-skills --skill ${skill.name}`}
                    />
                  </div>
                  <details>
                    <summary>
                      Try an example request <span aria-hidden="true">+</span>
                    </summary>
                    <blockquote>{skill.example}</blockquote>
                    <p className="skill-note">{skill.note}</p>
                  </details>
                </div>
              </article>
            ))}
            <p className="catalog-note">
              <span aria-hidden="true">↳</span> This collection grows by
              selection. Each new skill is deliberately promoted into the
              repository.
            </p>
          </div>
        </section>
        <section className="getting-started wrap" id="getting-started">
          <div className="section-heading">
            <div>
              <p className="eyebrow">A few minutes to begin</p>
              <h2>Find a skill. Put it to work.</h2>
            </div>
            <a className="text-link" href="https://skills.sh/docs">
              About skills.sh <span aria-hidden="true">↗</span>
            </a>
          </div>
          <div className="steps">
            <div>
              <span className="step-label">01 / CHOOSE</span>
              <h3>Start with your task.</h3>
              <p>
                Read what the skill does and check its requirements. Install
                only what is useful for your workflow.
              </p>
            </div>
            <div>
              <span className="step-label">02 / INSTALL</span>
              <h3>One command, your agent.</h3>
              <p>
                Run the skill’s install command with Node.js and npm available.
                The installer lets you choose your agent. Add{" "}
                <code>--global</code> to use it across projects.
              </p>
            </div>
            <div>
              <span className="step-label">03 / USE</span>
              <h3>Ask for the work.</h3>
              <p>
                Give your agent a task and mention the skill by name. Its
                instructions and supporting tools are there when the task needs
                them.
              </p>
            </div>
          </div>
          <details className="manual-install">
            <summary>
              Prefer to install manually? <span aria-hidden="true">+</span>
            </summary>
            <p>
              Copy the complete folder from{" "}
              <a href={`${repo}/tree/main/skills`}>
                the repository’s skills directory
              </a>{" "}
              into your agent’s supported skills directory. Keep scripts and
              references alongside <code>SKILL.md</code>. The website is not
              required to use a skill.
            </p>
          </details>
        </section>
        <section className="about wrap" id="about">
          <div>
            <p className="eyebrow">Small by intention</p>
            <h2>A collection worth keeping.</h2>
          </div>
          <div>
            <p>
              Agent Skills is maintained by{" "}
              <a href="https://github.com/ammar-hasan">Ammar Hasan</a>. It is a
              home for selected workflows we want to keep improving and share
              with others.
            </p>
            <p>
              Every skill uses the open{" "}
              <a href="https://agentskills.io/specification">
                Agent Skills format
              </a>
              . Read the source, suggest a fix, or adapt it to the way you work.
            </p>
            <a className="text-link" href={`${repo}/blob/main/CONTRIBUTING.md`}>
              Help improve the collection <span aria-hidden="true">↗</span>
            </a>
          </div>
        </section>
      </main>
      <footer className="site-footer wrap">
        <a className="brand" href="/agent-skills/">
          Agent Skills<span className="footer-dot">.</span>
        </a>
        <p>Made to be useful. Shared with care.</p>
        <div>
          <a href={`${repo}/blob/main/LICENSE`}>MIT License</a>
          <a href={repo}>Source ↗</a>
        </div>
      </footer>
    </>
  );
}
